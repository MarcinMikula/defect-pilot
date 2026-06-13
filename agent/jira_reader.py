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
    attachment_id: str = ""     # Jira attachment ID — used to download content


@dataclass
class JiraComment:
    author: str
    body: str           # ADF → plain text
    created: str


@dataclass
class JiraIssueLink:
    """
    Represents a link between two Jira issues.
    Link type names are locale/config-dependent — never hardcode.
    Examples: "Blocks", "is blocked by", "relates to", "Blokuje" (PL)
    """
    link_type: str              # e.g. "Blocks", "relates to"
    direction: str              # "inward" | "outward"
    related_issue_key: str
    related_issue_summary: str | None = None


@dataclass
class JiraDefect:
    """Parsed representation of a Jira issue."""

    issue_key: str
    summary: str
    description: str            # ADF → plain text
    status: str
    issue_type: str             # Raw name — locale-dependent ("Bug", "Błąd", "Defect", etc.)
    priority: str
    reporter: str
    assignee: str | None
    environment: str
    labels: list[str] = field(default_factory=list)
    attachments: list[JiraAttachment] = field(default_factory=list)
    comments: list[JiraComment] = field(default_factory=list)
    issue_links: list[JiraIssueLink] = field(default_factory=list)
    sprint: str | None = None
    raw: dict = field(default_factory=dict)     # Full raw Jira REST payload


# ---------------------------------------------------------------------------
# ADF → plain text + media extraction
# ---------------------------------------------------------------------------

def _adf_to_text(node: dict | None, _media_ids: list | None = None) -> str:
    """
    Recursively convert Atlassian Document Format (ADF) JSON to plain text.
    Jira Cloud REST API v3 returns description/comments as ADF, not plain text.

    Handles mediaSingle/media nodes — images embedded directly in description.
    Testers often paste screenshots straight into the description field (drag & drop)
    instead of using the attachment panel. Both cases end up as ADF media nodes
    AND in the attachment list, but we collect IDs here for completeness.

    Args:
        node: ADF node dict
        _media_ids: list to collect attachment IDs found in media nodes (mutated in place)
    """
    if not node:
        return ""

    node_type = node.get("type", "")
    content = node.get("content", [])
    text = node.get("text", "")

    if node_type == "text":
        return text

    # mediaSingle wraps a media node — image pasted/embedded in description
    # attrs.id is the attachment ID → /rest/api/3/attachment/content/{id}
    if node_type in ("mediaSingle", "media"):
        attrs = node.get("attrs", {})
        media_id = attrs.get("id")
        if media_id and _media_ids is not None:
            _media_ids.append(media_id)
        return ""   # No text to extract from an image node

    parts = [_adf_to_text(child, _media_ids) for child in content]

    if node_type in ("paragraph", "heading"):
        return " ".join(parts).strip() + "\n"
    if node_type in ("bulletList", "orderedList"):
        return "\n".join(parts)
    if node_type == "listItem":
        return "• " + " ".join(parts).strip()
    if node_type == "hardBreak":
        return "\n"

    return " ".join(parts)


def _extract_media_ids(adf_node: dict | None) -> list[str]:
    """Extract all attachment IDs embedded as media nodes in an ADF document."""
    media_ids: list[str] = []
    _adf_to_text(adf_node, _media_ids=media_ids)
    return media_ids


# ---------------------------------------------------------------------------
# Jira Reader
# ---------------------------------------------------------------------------

class JiraReader:
    """
    Reads and parses Jira issues via REST API v3.

    Auth: Basic auth (email + API token).
    Docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
    """

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
        "issuelinks",
        "customfield_10020",    # Sprint
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
            verify=False,
        )
        logger.info(f"[JiraReader] Initialized — {base_url}")

    def get_defect(self, issue_key: str) -> JiraDefect:
        """
        Fetch and parse a Jira issue.

        Args:
            issue_key: e.g. "STWA-5"

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

        logger.info(
            f"[JiraReader] Parsed {issue_key} — '{defect.summary}' [{defect.status}] "
            f"| attachments: {len(defect.attachments)} "
            f"| comments: {len(defect.comments)} "
            f"| links: {len(defect.issue_links)}"
        )
        return defect

    def download_attachment(self, attachment: JiraAttachment) -> bytes:
        """
        Download attachment content from Jira.
        Uses stored auth — works for images embedded in description too.

        Args:
            attachment: JiraAttachment with url set

        Returns:
            Raw bytes of the attachment
        """
        logger.info(f"[JiraReader] Downloading attachment: {attachment.filename}")
        response = self._client.get(attachment.url)
        response.raise_for_status()
        return response.content

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

        # Description — ADF → plain text + collect embedded media IDs
        description_adf = fields.get("description")
        embedded_media_ids = _extract_media_ids(description_adf)
        description = _adf_to_text(description_adf).strip()

        # Attachments from the attachment field
        attachments = [
            JiraAttachment(
                filename=att.get("filename", ""),
                url=att.get("content", ""),
                mime_type=att.get("mimeType", ""),
                size_bytes=att.get("size", 0),
                attachment_id=str(att.get("id", "")),
            )
            for att in fields.get("attachment", [])
        ]

        # Merge embedded media IDs — tester may paste screenshot into description
        # These show up as ADF media nodes AND in attachment list (same ID)
        # Mark them so enricher knows which ones are inline screenshots
        existing_ids = {a.attachment_id for a in attachments}
        for media_id in embedded_media_ids:
            if media_id not in existing_ids:
                # Embedded but not in attachment list — add with minimal info
                attachments.append(JiraAttachment(
                    filename=f"embedded_{media_id}.png",
                    url=f"/rest/api/3/attachment/content/{media_id}",
                    mime_type="image/png",
                    size_bytes=0,
                    attachment_id=media_id,
                ))

        # Comments
        comments = [
            JiraComment(
                author=(c.get("author") or {}).get("displayName", "Unknown"),
                body=_adf_to_text(c.get("body")).strip(),
                created=c.get("created", ""),
            )
            for c in (fields.get("comment") or {}).get("comments", [])
        ]

        # Issue links — locale-agnostic, store raw link type name
        issue_links = []
        for link in fields.get("issuelinks", []):
            link_type_name = (link.get("type") or {}).get("name", "Unknown")

            if "inwardIssue" in link:
                related = link["inwardIssue"]
                issue_links.append(JiraIssueLink(
                    link_type=link_type_name,
                    direction="inward",
                    related_issue_key=related.get("key", ""),
                    related_issue_summary=(related.get("fields") or {}).get("summary"),
                ))
            if "outwardIssue" in link:
                related = link["outwardIssue"]
                issue_links.append(JiraIssueLink(
                    link_type=link_type_name,
                    direction="outward",
                    related_issue_key=related.get("key", ""),
                    related_issue_summary=(related.get("fields") or {}).get("summary"),
                ))

        # Sprint (customfield_10020) — take last (active) sprint
        sprint = None
        sprint_field = fields.get("customfield_10020")
        if sprint_field and isinstance(sprint_field, list) and sprint_field:
            sprint = sprint_field[-1].get("name")

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
            comments=comments,
            issue_links=issue_links,
            sprint=sprint,
            raw=data,
        )
