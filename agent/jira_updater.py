"""
[DOMAIN: GENERIC]
Jira Updater — writes enriched defect data back to Jira.
Sprint 4 implementation target.
"""

import logging

from agent.jira_reader import JiraDefect

logger = logging.getLogger(__name__)


class JiraUpdater:
    """
    Updates Jira issue with enriched data and retest script link.

    TODO Sprint 4:
    - Update description with enriched steps
    - Add comment with generated Playwright script
    - Transition issue status if configured
    """

    def __init__(self, base_url: str, email: str, api_token: str):
        self._base_url = base_url.rstrip("/")
        self._email = email
        self._api_token = api_token
        logger.info("[JiraUpdater] Initialized (stub)")

    def update_defect(self, defect: JiraDefect, retest_script: str) -> None:
        """
        Push enriched data + retest script back to Jira.

        Args:
            defect: Enriched JiraDefect
            retest_script: Generated Playwright script as string
        """
        # TODO Sprint 4: implement
        logger.info(f"[JiraUpdater] Updating {defect.issue_key} (stub)")
        raise NotImplementedError("JiraUpdater.update_defect — Sprint 4")
