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


# ---------------------------------------------------------------------------
# Comments & Issue Links — fixtures
# ---------------------------------------------------------------------------

def make_comment_field(author: str, text: str, created: str = "2026-06-10T10:00:00.000+0000") -> dict:
    return {
        "author": {"displayName": author},
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": text}]}
            ],
        },
        "created": created,
    }


def make_issue_link(link_type: str, direction: str, related_key: str, summary: str | None = None) -> dict:
    related = {"key": related_key, "fields": {"summary": summary} if summary else {}}
    link = {"type": {"name": link_type}}
    if direction == "inward":
        link["inwardIssue"] = related
    else:
        link["outwardIssue"] = related
    return link


# ---------------------------------------------------------------------------
# Comments parsing
# ---------------------------------------------------------------------------

class TestCommentsParsing:
    def _mock_response(self, payload: dict):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        mock_resp.text = ""
        return mock_resp

    def _payload_with_comments(self, comments: list) -> dict:
        base = make_jira_response()
        base["fields"]["comment"] = {"comments": comments}
        return base

    def test_parses_single_comment(self):
        reader = make_reader()
        payload = self._payload_with_comments([
            make_comment_field("Marcin Nowak", "This is blocked by STWA-1")
        ])
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-2")
        assert len(defect.comments) == 1
        assert defect.comments[0].author == "Marcin Nowak"
        assert "blocked" in defect.comments[0].body

    def test_parses_multiple_comments(self):
        reader = make_reader()
        payload = self._payload_with_comments([
            make_comment_field("Alice", "First comment"),
            make_comment_field("Bob", "Second comment"),
            make_comment_field("Alice", "Third comment"),
        ])
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-2")
        assert len(defect.comments) == 3
        assert defect.comments[1].author == "Bob"

    def test_empty_comments_returns_empty_list(self):
        reader = make_reader()
        payload = make_jira_response()
        payload["fields"]["comment"] = {"comments": []}
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert defect.comments == []

    def test_missing_comment_field_returns_empty_list(self):
        reader = make_reader()
        payload = make_jira_response()
        payload["fields"].pop("comment", None)
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert defect.comments == []


# ---------------------------------------------------------------------------
# Issue links parsing
# ---------------------------------------------------------------------------

class TestIssueLinksParsing:
    def _mock_response(self, payload: dict):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        mock_resp.text = ""
        return mock_resp

    def _payload_with_links(self, links: list) -> dict:
        base = make_jira_response()
        base["fields"]["issuelinks"] = links
        return base

    def test_parses_inward_link(self):
        reader = make_reader()
        payload = self._payload_with_links([
            make_issue_link("Blocks", "inward", "STWA-1", "Login button broken")
        ])
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-2")
        assert len(defect.issue_links) == 1
        assert defect.issue_links[0].related_issue_key == "STWA-1"
        assert defect.issue_links[0].direction == "inward"
        assert defect.issue_links[0].link_type == "Blocks"

    def test_parses_outward_link(self):
        reader = make_reader()
        payload = self._payload_with_links([
            make_issue_link("Blocks", "outward", "STWA-3", "Related issue")
        ])
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-2")
        assert defect.issue_links[0].direction == "outward"
        assert defect.issue_links[0].related_issue_key == "STWA-3"

    def test_parses_related_issue_summary(self):
        reader = make_reader()
        payload = self._payload_with_links([
            make_issue_link("Blocks", "inward", "STWA-1", "Login button broken")
        ])
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-2")
        assert defect.issue_links[0].related_issue_summary == "Login button broken"

    def test_locale_agnostic_link_type(self):
        """Link type name should be stored as-is — no hardcoding or translation."""
        reader = make_reader()
        payload = self._payload_with_links([
            make_issue_link("Blokuje", "inward", "STWA-1")   # Polish locale
        ])
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-2")
        assert defect.issue_links[0].link_type == "Blokuje"

    def test_empty_links_returns_empty_list(self):
        reader = make_reader()
        payload = self._payload_with_links([])
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert defect.issue_links == []

    def test_missing_links_field_returns_empty_list(self):
        reader = make_reader()
        payload = make_jira_response()
        payload["fields"].pop("issuelinks", None)
        reader._client.get = MagicMock(return_value=self._mock_response(payload))

        defect = reader.get_defect("STWA-1")
        assert defect.issue_links == []
