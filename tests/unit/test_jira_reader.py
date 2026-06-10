"""
Unit tests for agent/jira_reader.py
All Jira API calls mocked — no real network needed.
"""

import pytest
from unittest.mock import MagicMock, patch

from agent.jira_reader import (
    JiraReader,
    JiraDefect,
    JiraAuthError,
    JiraNotFoundError,
    JiraError,
    _adf_to_text,
)


# ---------------------------------------------------------------------------
# ADF → plain text
# ---------------------------------------------------------------------------

class TestAdfToText:
    def test_returns_empty_on_none(self):
        assert _adf_to_text(None) == ""

    def test_simple_paragraph(self):
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello world"}],
                }
            ],
        }
        result = _adf_to_text(adf)
        assert "Hello world" in result

    def test_bullet_list(self):
        adf = {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Step 1"}]}
                    ],
                },
                {
                    "type": "listItem",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Step 2"}]}
                    ],
                },
            ],
        }
        result = _adf_to_text(adf)
        assert "Step 1" in result
        assert "Step 2" in result

    def test_empty_doc(self):
        adf = {"type": "doc", "content": []}
        assert _adf_to_text(adf).strip() == ""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_jira_response(
    issue_key="STWA-1",
    summary="Button does not work",
    description_text="Click Save, nothing happens",
    status="To Do",
    reporter="Marcin Nowak",
    assignee="Marcin Nowak",
    labels=None,
    attachments=None,
    sprint_name="STWA Sprint 1",
) -> dict:
    """Build a realistic Jira REST API v3 response payload."""
    return {
        "id": "10231",
        "key": issue_key,
        "fields": {
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description_text}],
                    }
                ],
            },
            "status": {"name": status},
            "issuetype": {"name": "Bug"},
            "priority": {"name": "Medium"},
            "reporter": {"displayName": reporter},
            "assignee": {"displayName": assignee} if assignee else None,
            "environment": "Salesforce DEV sandbox",
            "labels": labels or ["API"],
            "attachment": attachments or [],
            "customfield_10020": [{"name": sprint_name}] if sprint_name else None,
        },
    }


def make_reader() -> JiraReader:
    return JiraReader(
        base_url="https://test.atlassian.net",
        email="test@test.com",
        api_token="fake-token",
    )


# ---------------------------------------------------------------------------
# JiraReader.get_defect — happy path
# ---------------------------------------------------------------------------

class TestGetDefect:
    def _mock_response(self, payload: dict, status_code: int = 200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = payload
        mock_resp.text = ""
        return mock_resp

    def test_parses_summary(self):
        reader = make_reader()
        payload = make_jira_response(summary="Login button broken")
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert defect.summary == "Login button broken"

    def test_parses_issue_key(self):
        reader = make_reader()
        payload = make_jira_response(issue_key="STWA-42")
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-42")
        assert defect.issue_key == "STWA-42"

    def test_parses_status(self):
        reader = make_reader()
        payload = make_jira_response(status="In Progress")
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert defect.status == "In Progress"

    def test_parses_description_from_adf(self):
        reader = make_reader()
        payload = make_jira_response(description_text="Click Save button on Account page")
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert "Click Save" in defect.description

    def test_parses_labels(self):
        reader = make_reader()
        payload = make_jira_response(labels=["API", "Salesforce"])
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert "API" in defect.labels
        assert "Salesforce" in defect.labels

    def test_parses_sprint(self):
        reader = make_reader()
        payload = make_jira_response(sprint_name="STWA Sprint 1")
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert defect.sprint == "STWA Sprint 1"

    def test_handles_no_assignee(self):
        reader = make_reader()
        payload = make_jira_response(assignee=None)
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert defect.assignee is None

    def test_raw_payload_stored(self):
        reader = make_reader()
        payload = make_jira_response()
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert defect.raw == payload

    def test_parses_attachments(self):
        reader = make_reader()
        attachments = [
            {
                "filename": "screenshot.png",
                "content": "https://test.atlassian.net/attach/screenshot.png",
                "mimeType": "image/png",
                "size": 12345,
            }
        ]
        payload = make_jira_response(attachments=attachments)
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert len(defect.attachments) == 1
        assert defect.attachments[0].filename == "screenshot.png"
        assert defect.attachments[0].mime_type == "image/png"


# ---------------------------------------------------------------------------
# JiraReader.get_defect — error handling
# ---------------------------------------------------------------------------

class TestGetDefectErrors:
    def _mock_error_response(self, status_code: int, text: str = "error") -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.text = text
        mock_resp.json.return_value = {}
        return mock_resp

    def test_raises_auth_error_on_401(self):
        reader = make_reader()
        reader._client.get = MagicMock(return_value=self._mock_error_response(401))

        with pytest.raises(JiraAuthError, match="authentication failed"):
            reader.get_defect("STWA-1")

    def test_raises_not_found_on_404(self):
        reader = make_reader()
        reader._client.get = MagicMock(return_value=self._mock_error_response(404))

        with pytest.raises(JiraNotFoundError, match="not found"):
            reader.get_defect("STWA-99")

    def test_raises_jira_error_on_500(self):
        reader = make_reader()
        reader._client.get = MagicMock(return_value=self._mock_error_response(500, "Server Error"))

        with pytest.raises(JiraError):
            reader.get_defect("STWA-1")
