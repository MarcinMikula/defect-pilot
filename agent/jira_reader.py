"""
[DOMAIN: GENERIC]
Jira Reader — connects to Jira Cloud API and reads defect data.
Sprint 1 implementation target.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class JiraDefect:
    """Parsed representation of a Jira issue."""

    issue_key: str
    summary: str
    description: str
    status: str
    reporter: str
    assignee: str | None
    steps_to_reproduce: str
    expected_result: str
    actual_result: str
    environment: str
    attachments: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # Full raw Jira payload


class JiraReader:
    """
    Reads and parses Jira defects.

    TODO Sprint 1:
    - Connect to Jira Cloud REST API v3
    - Parse standard defect fields
    - Extract attachments (screenshots)
    - Handle custom fields (steps, expected/actual)
    """

    def __init__(self, base_url: str, email: str, api_token: str):
        self._base_url = base_url.rstrip("/")
        self._email = email
        self._api_token = api_token
        # TODO Sprint 1: initialize httpx client with basic auth
        logger.info("[JiraReader] Initialized (stub)")

    def get_defect(self, issue_key: str) -> JiraDefect:
        """
        Fetch and parse a Jira issue.

        Args:
            issue_key: e.g. "PROJ-123"

        Returns:
            Parsed JiraDefect

        Raises:
            JiraNotFoundError: If issue doesn't exist
            JiraAuthError: If credentials are invalid
        """
        # TODO Sprint 1: implement
        logger.info(f"[JiraReader] Fetching {issue_key} (stub)")
        raise NotImplementedError("JiraReader.get_defect — Sprint 1")
