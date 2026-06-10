"""
[DOMAIN: GENERIC]
Defect Enricher — uses AI to add technical context to a Jira defect.
Sprint 2 implementation target.
"""

import logging

from agent.jira_reader import JiraDefect
from ai.base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


class DefectEnricher:
    """
    Uses AI to enrich a defect with:
    - Structured reproduction steps
    - Suggested DOM selectors / element IDs
    - HTTP request context (if available)
    - Playwright-friendly action sequence

    TODO Sprint 2:
    - Prompt engineering for step extraction
    - Shadow DOM / Salesforce LWC awareness
    - Confidence scoring per enriched field
    """

    def __init__(self, ai_provider: BaseAIProvider):
        self._ai = ai_provider
        logger.info(f"[DefectEnricher] Initialized with provider: {ai_provider.provider_name}")

    def enrich(self, defect: JiraDefect) -> JiraDefect:
        """
        Analyze defect and return enriched version.

        Args:
            defect: Parsed JiraDefect from JiraReader

        Returns:
            Enriched JiraDefect with additional technical context
        """
        # TODO Sprint 2: implement prompt + parse response
        logger.info(f"[DefectEnricher] Enriching {defect.issue_key} (stub)")
        raise NotImplementedError("DefectEnricher.enrich — Sprint 2")
