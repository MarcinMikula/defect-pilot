"""
[DOMAIN: GENERIC]
Jira Reader — connects to Jira Cloud REST API v3 and reads issue data.
"""

import logging
from dataclasses import dataclass, field
from base64 import b64encode

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class JiraError(Exception):
    """Base Jira error."""


class JiraNotFoundError(JiraError):
    """Issue does not exist or is not accessible."""


class JiraAuthError(JiraError):
    """Invalid credentials or missing permissions."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class JiraAttachment:
    filename: str
    url: str
    mime_type: str
    size_bytes: int


@dataclass
class JiraDefect:
    """Parsed representation of a Jira issue."""

    issue_key: str
    summary: str
    description: str          # Raw description text (Atlassian Document Format → plain text)
    status: str
    issue_type: str
    priority: str
    reporter: str
    assignee: str | None
    environment: str
    labels: list[str] = field(default_factory=list)
    attachments: list[JiraAttachment] = field(default_factory=list)
    sprint: str | None = None
    raw: dict = field(default_factory=dict)   # Full raw Jira REST payload


# ---------------------------------------------------------------------------
# ADF → plain text helper
# ---------------------------------------------------------------------------

def _adf_to_text(node: dict | None) -> str:
    """
    Recursively convert Atlassian Document Format (ADF) JSON to plain text.
    Jira Cloud REST API v3 returns description as ADF, not plain text.
    """
    if not node:
        return ""

    node_type = node.get("type", "")
    content = node.get("content", [])
    text = node.get("text", "")

    if node_type == "text":
        return text

    parts = [_adf_to_text(child) for child in content]

    if node_type in ("paragraph", "heading"):
        return " ".join(parts).strip() + "\n"
    if node_type in ("bulletList", "orderedList"):
        return "\n".join(parts)
    if node_type == "listItem":
        return "• " + " ".join(parts).strip()
    if node_type == "hardBreak":
        return "\n"

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Jira Reader
# ---------------------------------------------------------------------------

class JiraReader:
    """
    Reads and parses Jira issues via REST API v3.

    Auth: Basic auth (email + API token).
    Docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
    """

    # Jira REST API v3 fields we care about
    _FIELDS = [
        "summary",
        "description",
        "status",
        "issuetype",
        "priority",
        "reporter",
        "assignee",
        "environment",
        "labels",
        "attachment",
        "comment",
        "customfield_10020",  # Sprint
    ]

    def __init__(self, base_url: str, email: str, api_token: str):
        self._base_url = base_url.rstrip("/")
        token = b64encode(f"{email}:{api_token}".encode()).decode()
        self._client = httpx.Client(
            base_url=f"{self._base_url}/rest/api/3",
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        logger.info(f"[JiraReader] Initialized — {base_url}")

    def get_defect(self, issue_key: str) -> JiraDefect:
        """
        Fetch and parse a Jira issue.

        Args:
            issue_key: e.g. "STWA-1"

        Returns:
            Parsed JiraDefect

        Raises:
            JiraNotFoundError: Issue doesn't exist or no access
            JiraAuthError: Invalid credentials
            JiraError: Other API errors
        """
        logger.info(f"[JiraReader] Fetching {issue_key}")

        fields_param = ",".join(self._FIELDS)
        response = self._client.get(f"/issue/{issue_key}?fields={fields_param}")

        self._handle_errors(response, issue_key)

        data = response.json()
        defect = self._parse(issue_key, data)

        logger.info(f"[JiraReader] Parsed {issue_key} — '{defect.summary}' [{defect.status}]")
        return defect

    def check_connection(self) -> bool:
        """Verify Jira connectivity and credentials."""
        try:
            response = self._client.get("/myself")
            if response.status_code == 200:
                user = response.json().get("displayName", "unknown")
                logger.info(f"[JiraReader] Connected as: {user}")
                return True
            return False
        except Exception as e:
            logger.warning(f"[JiraReader] Connection check failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_errors(self, response: httpx.Response, issue_key: str) -> None:
        if response.status_code == 401:
            raise JiraAuthError(
                "Jira authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN in .env"
            )
        if response.status_code == 404:
            raise JiraNotFoundError(
                f"Issue '{issue_key}' not found. Check the issue key and project permissions."
            )
        if response.status_code >= 400:
            raise JiraError(
                f"Jira API error {response.status_code}: {response.text[:200]}"
            )

    def _parse(self, issue_key: str, data: dict) -> JiraDefect:
        fields = data.get("fields", {})

        # Core fields
        summary = fields.get("summary", "")
        status = fields.get("status", {}).get("name", "Unknown")
        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        priority = fields.get("priority", {}).get("name", "Medium")
        environment = fields.get("environment") or ""
        labels = fields.get("labels", [])

        # People
        reporter_obj = fields.get("reporter") or {}
        reporter = reporter_obj.get("displayName", "Unknown")
        assignee_obj = fields.get("assignee") or {}
        assignee = assignee_obj.get("displayName") if assignee_obj else None

        # Description — ADF → plain text
        description = _adf_to_text(fields.get("description")).strip()

        # Attachments
        attachments = [
            JiraAttachment(
                filename=att.get("filename", ""),
                url=att.get("content", ""),
                mime_type=att.get("mimeType", ""),
                size_bytes=att.get("size", 0),
            )
            for att in fields.get("attachment", [])
        ]

        # Sprint (customfield_10020)
        sprint = None
        sprint_field = fields.get("customfield_10020")
        if sprint_field and isinstance(sprint_field, list) and sprint_field:
            sprint = sprint_field[-1].get("name")  # Last (active) sprint

        return JiraDefect(
            issue_key=issue_key,
            summary=summary,
            description=description,
            status=status,
            issue_type=issue_type,
            priority=priority,
            reporter=reporter,
            assignee=assignee,
            environment=environment,
            labels=labels,
            attachments=attachments,
            sprint=sprint,
            raw=data,
        )
