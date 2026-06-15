"""
[DOMAIN: GENERIC]
Defect Enricher — uses AI to analyze a Jira defect and extract structured
technical context for developers and retest script generation.

Supports multimodal input: text description + screenshots (base64).
Works with both Anthropic (Claude) and Ollama (local LLM).
"""

import base64
import logging
import re
from dataclasses import dataclass, field

from agent.jira_reader import JiraAttachment, JiraDefect
from ai.base_provider import BaseAIProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class EnrichedDefect:
    """
    AI-enriched defect — structured output ready for Playwright script generation
    and Jira update.
    """
    issue_key: str
    summary: str

    # Structured reproduction steps extracted/inferred by AI
    steps_to_reproduce: list[str] = field(default_factory=list)

    # Expected vs actual
    expected_result: str = ""
    actual_result: str = ""

    # Technical context extracted from screenshot + description
    url: str = ""                          # URL where bug occurred (if detectable)
    ui_elements: list[str] = field(default_factory=list)   # Buttons, fields, selectors mentioned
    error_message: str = ""               # Error text visible in screenshot/description
    requirement_refs: list[str] = field(default_factory=list)  # e.g. ["OPL-SF-008"]

    # Quality assessment
    completeness_score: int = 0           # 0-100: how complete is this defect report
    missing_info: list[str] = field(default_factory=list)  # What's missing for reproduction

    # Screenshots analyzed
    screenshots_analyzed: int = 0

    # Raw AI response for debugging
    raw_ai_response: str = ""


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior QA engineer and test automation expert.
Your job is to analyze bug reports written by manual testers (often incomplete)
and extract structured technical information needed to reproduce the bug
and write automated retest scripts.

CRITICAL RULES:
- You MUST respond using EXACTLY the section headers shown — do not skip any section
- You MUST provide a value for every section — never leave a section empty
- If information is not available, write "Unknown" or "Not visible" — never leave blank
- Always respond in the same language as the bug report (Polish or English)
- If screenshots are provided, describe what you see: UI state, error messages, URL in browser bar
- Be practical and specific — avoid vague statements

ENVIRONMENT ASSUMPTIONS (do not penalize for missing these):
- Default browser: Chrome
- Default OS: Windows
- Application URL provided in description counts as full environment specification
- Do NOT mark environment as missing if a URL is present in the report
"""

ANALYSIS_PROMPT_TEMPLATE = """Analyze this bug report and extract structured information.
You MUST fill in ALL sections. Do not skip any section.

## Bug Report

**Issue:** {issue_key}
**Summary:** {summary}
**Status:** {status}
**Priority:** {priority}
**Reporter:** {reporter}
**Environment:** {environment}
**Labels:** {labels}
**Sprint:** {sprint}

**Description:**
{description}

**Comments:**
{comments}

**Linked Issues:**
{issue_links}

{requirement_context}

{screenshot_note}

---

YOU MUST respond with ALL sections below in EXACTLY this format.
Fill every section — write "Unknown" if information is missing, never leave blank:

### KROKI REPRODUKCJI / STEPS TO REPRODUCE
1. (first step — infer from context and screenshots)
2. (next step)
3. (continue until bug is triggered)

### EXPECTED RESULT
(what should happen when steps are followed correctly)

### ACTUAL RESULT
(what actually happens — describe error visible in screenshot if provided)

### URL
(URL visible in screenshot browser bar, or from description, or "Unknown")

### ELEMENTY UI / UI ELEMENTS
- (button, field, or element name — one per line)

### KOMUNIKAT BŁĘDU / ERROR MESSAGE
(exact error text visible in screenshot or description, or "Not visible")

### POWIĄZANE WYMAGANIA / REQUIREMENT REFS
(requirement codes like OPL-SF-008 or linked issue keys found in title/description, or "None")

### BRAKUJĄCE INFORMACJE / MISSING INFO
- (what information is missing to fully reproduce this bug — do NOT list browser or OS)

### KOMPLETNOŚĆ / COMPLETENESS SCORE
(single integer 0-100, where 100 = perfectly reproducible without asking questions)
"""

# ---------------------------------------------------------------------------
# Heuristic scoring weights
# Used as fallback when AI returns 0 (model too strict) or fails to parse score.
# Each field contributes points toward a max of 100.
# ---------------------------------------------------------------------------

_SCORE_WEIGHTS = {
    "steps_to_reproduce": 25,   # Most important — without steps can't reproduce
    "url": 20,                  # URL = environment for web apps
    "expected_result": 15,      # Needed to judge pass/fail
    "actual_result": 15,        # What actually went wrong
    "screenshots_analyzed": 10, # Visual evidence
    "ui_elements": 10,          # Selector/element info for automation
    "requirement_refs": 5,      # Nice to have — traceability
}


# ---------------------------------------------------------------------------
# Enricher
# ---------------------------------------------------------------------------

class DefectEnricher:
    """
    Uses AI to analyze a Jira defect and return structured EnrichedDefect.

    Multimodal: if defect has image attachments, they are downloaded
    and sent to AI as base64 for visual analysis.

    Works with both AnthropicProvider (vision supported) and
    OllamaProvider (text-only fallback if model doesn't support vision).
    """

    def __init__(self, ai_provider: BaseAIProvider, jira_reader=None):
        """
        Args:
            ai_provider: Configured AI provider (Anthropic or Ollama)
            jira_reader: JiraReader instance for downloading attachments
                         and fetching linked issues.
                         If None, screenshots and linked issues won't be fetched.
        """
        self._ai = ai_provider
        self._jira_reader = jira_reader
        logger.info(f"[DefectEnricher] Initialized with provider: {ai_provider.provider_name}")

    def enrich(self, defect: JiraDefect) -> EnrichedDefect:
        """
        Analyze defect and return enriched structured version.

        Args:
            defect: Parsed JiraDefect from JiraReader

        Returns:
            EnrichedDefect with structured technical context
        """
        logger.info(f"[DefectEnricher] Enriching {defect.issue_key}")

        # Download image attachments if JiraReader available
        images_b64 = self._collect_screenshots(defect)
        logger.info(
            f"[DefectEnricher] {len(images_b64)} screenshot(s) collected for analysis"
        )

        # Fetch linked issues (requirements, epics) for additional context
        linked_issues: dict = {}
        if self._jira_reader and defect.issue_links:
            linked_issues = self._jira_reader.get_linked_issues(defect.issue_links)
            if linked_issues:
                logger.info(
                    f"[DefectEnricher] Fetched {len(linked_issues)} linked issue(s): "
                    + ", ".join(linked_issues.keys())
                )

        # Build prompt
        prompt = self._build_prompt(defect, has_images=len(images_b64) > 0, linked_issues=linked_issues)

        # Call AI — with or without images
        if images_b64 and hasattr(self._ai, "complete_with_images"):
            raw_response = self._ai.complete_with_images(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                images_b64=images_b64,
            ).content
        else:
            if images_b64:
                logger.warning(
                    "[DefectEnricher] Provider doesn't support vision — "
                    "analyzing text only. Screenshots ignored."
                )
            raw_response = self._ai.complete(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            ).content

        # Parse structured response
        enriched = self._parse_response(defect, raw_response, len(images_b64))
        logger.info(
            f"[DefectEnricher] {defect.issue_key} enriched — "
            f"completeness: {enriched.completeness_score}/100 | "
            f"steps: {len(enriched.steps_to_reproduce)} | "
            f"missing: {len(enriched.missing_info)}"
        )
        return enriched

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_screenshots(self, defect: JiraDefect) -> list[str]:
        """Download image attachments and return as base64 strings."""
        if not self._jira_reader:
            return []

        images = []
        for att in defect.attachments:
            if not self._is_image(att):
                continue
            try:
                raw = self._jira_reader.download_attachment(att)
                images.append(base64.b64encode(raw).decode())
                logger.debug(f"[DefectEnricher] Downloaded: {att.filename}")
            except Exception as e:
                logger.warning(
                    f"[DefectEnricher] Failed to download {att.filename}: {e}"
                )
        return images

    def _is_image(self, att: JiraAttachment) -> bool:
        image_mimes = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        if att.mime_type.lower() in image_mimes:
            return True
        return any(att.filename.lower().endswith(ext) for ext in image_exts)

    def _build_prompt(self, defect: JiraDefect, has_images: bool, linked_issues: dict) -> str:
        comments_text = "\n".join(
            f"- [{c.author}]: {c.body}" for c in defect.comments
        ) or "None"

        links_text = "\n".join(
            f"- {l.link_type} ({l.direction}): {l.related_issue_key}"
            + (f" — {l.related_issue_summary}" if l.related_issue_summary else "")
            for l in defect.issue_links
        ) or "None"

        # Requirement context — full description of linked issues
        requirement_context = ""
        if linked_issues:
            parts = ["**Requirement Details (from linked issues):**"]
            for key, issue in linked_issues.items():
                parts.append(
                    f"\n[{key}] {issue.issue_type}: {issue.summary}\n"
                    f"{issue.description or 'No description.'}"
                )
            requirement_context = "\n".join(parts)

        screenshot_note = (
            "**Screenshots:** Attached above — analyze them for error messages, "
            "UI state, and element names."
            if has_images
            else "**Screenshots:** None provided."
        )

        return ANALYSIS_PROMPT_TEMPLATE.format(
            issue_key=defect.issue_key,
            summary=defect.summary,
            status=defect.status,
            priority=defect.priority,
            reporter=defect.reporter,
            environment=defect.environment or "Not specified",
            labels=", ".join(defect.labels) or "None",
            sprint=defect.sprint or "Not specified",
            description=defect.description or "No description provided.",
            comments=comments_text,
            issue_links=links_text,
            requirement_context=requirement_context,
            screenshot_note=screenshot_note,
        )

    def _heuristic_score(self, enriched: "EnrichedDefect") -> int:
        """
        Calculate completeness score based on which fields were extracted.
        Used as fallback when AI returns 0 (model too strict) or score parsing fails.

        Weights defined in _SCORE_WEIGHTS — sum to 100.
        Returns int 0-100.
        """
        score = 0
        if enriched.steps_to_reproduce:
            score += _SCORE_WEIGHTS["steps_to_reproduce"]
        if enriched.url and enriched.url.lower() not in ("unknown", "nie podano"):
            score += _SCORE_WEIGHTS["url"]
        if enriched.expected_result and enriched.expected_result.lower() != "unknown":
            score += _SCORE_WEIGHTS["expected_result"]
        if enriched.actual_result and enriched.actual_result.lower() != "unknown":
            score += _SCORE_WEIGHTS["actual_result"]
        if enriched.screenshots_analyzed > 0:
            score += _SCORE_WEIGHTS["screenshots_analyzed"]
        if enriched.ui_elements:
            score += _SCORE_WEIGHTS["ui_elements"]
        if enriched.requirement_refs:
            score += _SCORE_WEIGHTS["requirement_refs"]
        return min(score, 100)

    def _parse_response(
        self, defect: JiraDefect, raw: str, screenshots_analyzed: int
    ) -> EnrichedDefect:
        """Parse AI structured response into EnrichedDefect."""

        result = EnrichedDefect(
            issue_key=defect.issue_key,
            summary=defect.summary,
            raw_ai_response=raw,
            screenshots_analyzed=screenshots_analyzed,
        )

        # Section extractors — look for ### HEADER then grab lines until next ###
        result.steps_to_reproduce = self._extract_list(raw, [
            "KROKI REPRODUKCJI", "STEPS TO REPRODUCE"
        ])
        result.expected_result = self._extract_value(raw, ["EXPECTED RESULT"])
        result.actual_result = self._extract_value(raw, ["ACTUAL RESULT"])
        result.url = self._extract_value(raw, ["URL"])
        result.ui_elements = self._extract_list(raw, ["ELEMENTY UI", "UI ELEMENTS"])
        result.error_message = self._extract_value(raw, ["KOMUNIKAT BŁĘDU", "ERROR MESSAGE"])
        result.requirement_refs = self._extract_list(raw, ["POWIĄZANE WYMAGANIA", "REQUIREMENT REFS"])
        result.missing_info = self._extract_list(raw, ["BRAKUJĄCE INFORMACJE", "MISSING INFO"])

        score_raw = self._extract_value(raw, ["KOMPLETNOŚĆ", "COMPLETENESS SCORE"])

        # Fallback: if section parser missed the score, scan raw response directly
        # Handles formats: "50", "KOMPLETNOŚĆ / COMPLETENESS SCORE\n50", "Score: 75/100"
        if not score_raw:
            match = re.search(r'(?:KOMPLETNO[ŚS][ĆC]|COMPLETENESS\s*SCORE)[^\d]*(\d{1,3})', raw, re.IGNORECASE)
            if match:
                score_raw = match.group(1)

        try:
            digits = re.search(r'\d{1,3}', score_raw)
            score = int(digits.group()) if digits else 0
            result.completeness_score = max(0, min(100, score))  # clamp 0-100
        except (ValueError, TypeError, AttributeError):
            result.completeness_score = 0

        # Heuristic fallback — if AI returned 0, calculate from extracted fields.
        # Prevents model strictness (penalizing missing OS/browser) from masking
        # reports that are actually well-formed and reproducible.
        # A true zero (empty report) will also score 0 here — no false positives.
        if result.completeness_score == 0:
            result.completeness_score = self._heuristic_score(result)
            if result.completeness_score > 0:
                logger.debug(
                    f"[DefectEnricher] AI score was 0 — heuristic fallback: "
                    f"{result.completeness_score}/100"
                )

        return result

    def _extract_value(self, text: str, headers: list[str]) -> str:
        """Extract single-value section content."""
        lines = self._extract_section_lines(text, headers)
        return " ".join(lines).strip()

    def _extract_list(self, text: str, headers: list[str]) -> list[str]:
        """Extract multi-line section as list of items."""
        lines = self._extract_section_lines(text, headers)
        items = []
        for line in lines:
            line = line.strip().lstrip("•-*0123456789. ").strip()
            if line and line.lower() not in ("none", "brak", "unknown", "nieznany"):
                items.append(line)
        return items

    def _extract_section_lines(self, text: str, headers: list[str]) -> list[str]:
        """
        Find section by any of the header variants and return its lines.
        Handles three formats:
          - Markdown:  ### HEADER TEXT        (Claude, structured LLMs)
          - Bold:      **HEADER TEXT**        (llava bold markdown)
          - Plain:     HEADER TEXT:           (llava, older models)
        """
        lines = text.split("\n")
        in_section = False
        result = []

        for line in lines:
            stripped = line.strip()
            is_header, matches = self._is_section_header(stripped, headers)

            if is_header:
                if matches:
                    in_section = True
                    continue
                elif in_section:
                    break  # Hit next section

            if in_section and stripped:
                # Skip parenthetical placeholders like (Unknown) or (Not visible)
                if stripped.startswith("(") and stripped.endswith(")"):
                    continue
                result.append(stripped)

        return result

    def _is_section_header(self, line: str, headers: list[str]) -> tuple[bool, bool]:
        """
        Check if line is a section header and whether it matches our headers.
        Returns (is_any_header, matches_our_headers).

        Supported formats:
          ### HEADER TEXT               — markdown (Claude)
          **HEADER TEXT**               — bold markdown (llava)
          **HEADER TEXT / ALT TEXT**    — bold with slash variant (llava)
          HEADER TEXT:                  — plain colon (older models)
        """
        all_keywords = [
            "KROKI", "STEPS", "EXPECTED", "ACTUAL", "URL",
            "ELEMENTY", "ELEMENTS", "KOMUNIKAT", "ERROR",
            "WYMAGANIA", "REQUIREMENT", "BRAKUJ", "MISSING",
            "KOMPLETNO", "COMPLETENESS", "SCORE"
        ]

        # Markdown format: ### HEADER
        if line.startswith("###"):
            header_text = line.lstrip("#").strip().upper()
            matches = any(h.upper() in header_text for h in headers)
            return True, matches

        # Bold markdown format: **HEADER** or **HEADER / ALT**
        bold_match = re.match(r'^\*\*(.+?)\*\*$', line)
        if bold_match:
            header_text = bold_match.group(1).strip().upper()
            if any(kw in header_text for kw in all_keywords):
                matches = any(h.upper() in header_text for h in headers)
                return True, matches

        # Plain format: HEADER: (llava style)
        if line.endswith(":") and len(line) > 3:
            header_text = line.rstrip(":").strip().upper()
            if any(kw in header_text for kw in all_keywords):
                matches = any(h.upper() in header_text for h in headers)
                return True, matches

        return False, False