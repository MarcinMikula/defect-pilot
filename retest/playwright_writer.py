"""
[DOMAIN: GENERIC]
Playwright Writer — generates retest scripts from enriched defect data.
Sprint 3 implementation target.

Key challenge: Shadow DOM support for Salesforce LWC components.
Playwright handles this via pierce selectors: >> pierce/[selector]
"""

import logging

from agent.jira_reader import JiraDefect
from ai.base_provider import BaseAIProvider

logger = logging.getLogger(__name__)

# Playwright pierce selector syntax for Shadow DOM
# Usage: page.locator("pierce/#component-id")
SHADOW_DOM_NOTE = """
# NOTE: Salesforce LWC components use Shadow DOM.
# Selectors use Playwright's pierce syntax: pierce/[selector]
# Example: page.locator("pierce/input[name='LastName']")
# SF component IDs may change between releases — regenerate if tests break.
"""


class PlaywrightWriter:
    """
    Generates Playwright Python retest scripts from enriched defects.

    TODO Sprint 3:
    - System prompt with Playwright best practices
    - Shadow DOM / Salesforce LWC handling
    - Script validation (syntax check before saving)
    - Output to /retest_scripts/{issue_key}_retest.py
    """

    def __init__(self, ai_provider: BaseAIProvider):
        self._ai = ai_provider
        logger.info(f"[PlaywrightWriter] Initialized with provider: {ai_provider.provider_name}")

    def generate_script(self, defect: JiraDefect) -> str:
        """
        Generate a Playwright retest script for the defect.

        Args:
            defect: Enriched JiraDefect

        Returns:
            Python Playwright script as string
        """
        # TODO Sprint 3: implement
        logger.info(f"[PlaywrightWriter] Generating script for {defect.issue_key} (stub)")
        raise NotImplementedError("PlaywrightWriter.generate_script — Sprint 3")
