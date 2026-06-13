"""
Unit tests for agent/defect_enricher.py
AI calls fully mocked — no real API needed.
"""

import pytest
from unittest.mock import MagicMock

from agent.defect_enricher import DefectEnricher, EnrichedDefect, SYSTEM_PROMPT
from agent.jira_reader import JiraDefect, JiraAttachment, JiraComment, JiraIssueLink
from ai.base_provider import AIResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_ai_response(content: str) -> AIResponse:
    return AIResponse(content=content, provider="mock", model="mock-model")


def make_mock_provider(response_text: str) -> MagicMock:
    provider = MagicMock()
    provider.provider_name = "mock"
    provider.complete.return_value = make_ai_response(response_text)
    return provider


def make_defect(
    issue_key: str = "STWA-5",
    summary: str = "Błąd przy tworzeniu konta",
    description: str = "Testowałem OPL-SF-008. Kliknąłem Zapisz — dostałem błąd.",
    attachments: list = None,
    comments: list = None,
    issue_links: list = None,
) -> JiraDefect:
    return JiraDefect(
        issue_key=issue_key,
        summary=summary,
        description=description,
        status="Do zrobienia",
        issue_type="Błąd",
        priority="Medium",
        reporter="Marcin Nowak",
        assignee="Marcin Nowak",
        environment="Salesforce DEV",
        labels=["AI"],
        attachments=attachments or [],
        comments=comments or [],
        issue_links=issue_links or [],
        sprint="STWA Sprint 1",
    )


SAMPLE_AI_RESPONSE = """
### KROKI REPRODUKCJI / STEPS TO REPRODUCE
1. Zaloguj się do Salesforce
2. Przejdź do Accounts → New
3. Wybierz typ: Klient indywidualny
4. Wypełnij pole PESEL
5. Kliknij Zapisz

### EXPECTED RESULT
Konto klienta zostało zapisane pomyślnie.

### ACTUAL RESULT
Pojawił się błąd walidacji po kliknięciu Zapisz.

### URL
https://salesforce.com/lightning/o/Account/new

### ELEMENTY UI / UI ELEMENTS
- Przycisk Zapisz
- Pole PESEL
- Formularz konta indywidualnego

### KOMUNIKAT BŁĘDU / ERROR MESSAGE
Pole PESEL zawiera nieprawidłową wartość.

### POWIĄZANE WYMAGANIA / REQUIREMENT REFS
OPL-SF-008

### BRAKUJĄCE INFORMACJE / MISSING INFO
- Nazwa przeglądarki i wersja
- Dane testowe (konkretny numer PESEL)
- Środowisko (DEV/UAT/PROD)

### KOMPLETNOŚĆ / COMPLETENESS SCORE
45
"""


# ---------------------------------------------------------------------------
# Basic enrichment
# ---------------------------------------------------------------------------

class TestDefectEnricher:
    def test_returns_enriched_defect(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert isinstance(result, EnrichedDefect)
        assert result.issue_key == "STWA-5"

    def test_parses_steps_to_reproduce(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert len(result.steps_to_reproduce) == 5
        assert "Zaloguj się do Salesforce" in result.steps_to_reproduce[0]

    def test_parses_expected_result(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert "Konto klienta" in result.expected_result

    def test_parses_actual_result(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert "błąd walidacji" in result.actual_result

    def test_parses_url(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert "salesforce.com" in result.url

    def test_parses_ui_elements(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert len(result.ui_elements) == 3
        assert any("Zapisz" in e for e in result.ui_elements)

    def test_parses_error_message(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert "PESEL" in result.error_message

    def test_parses_requirement_refs(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert "OPL-SF-008" in result.requirement_refs

    def test_parses_missing_info(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert len(result.missing_info) == 3
        assert any("przeglądark" in m.lower() for m in result.missing_info)

    def test_parses_completeness_score(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert result.completeness_score == 45

    def test_stores_raw_ai_response(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        result = enricher.enrich(make_defect())

        assert result.raw_ai_response == SAMPLE_AI_RESPONSE

    def test_calls_ai_with_system_prompt(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        enricher.enrich(make_defect())

        call_kwargs = provider.complete.call_args
        assert call_kwargs.kwargs.get("system_prompt") == SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Screenshot handling
# ---------------------------------------------------------------------------

class TestScreenshotHandling:
    def test_no_screenshots_when_no_jira_reader(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider, jira_reader=None)

        att = JiraAttachment(
            filename="screen.png",
            url="https://jira/attach/1",
            mime_type="image/png",
            size_bytes=1000,
            attachment_id="10033",
        )
        result = enricher.enrich(make_defect(attachments=[att]))

        assert result.screenshots_analyzed == 0

    def test_downloads_image_attachments(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        provider.complete_with_images = MagicMock(
            return_value=make_ai_response(SAMPLE_AI_RESPONSE)
        )

        jira_reader = MagicMock()
        jira_reader.download_attachment.return_value = b"fake_image_bytes"

        enricher = DefectEnricher(ai_provider=provider, jira_reader=jira_reader)

        att = JiraAttachment(
            filename="screen.png",
            url="https://jira/attach/1",
            mime_type="image/png",
            size_bytes=1000,
            attachment_id="10033",
        )
        result = enricher.enrich(make_defect(attachments=[att]))

        assert result.screenshots_analyzed == 1
        jira_reader.download_attachment.assert_called_once_with(att)

    def test_skips_non_image_attachments(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        jira_reader = MagicMock()

        enricher = DefectEnricher(ai_provider=provider, jira_reader=jira_reader)

        att = JiraAttachment(
            filename="logs.txt",
            url="https://jira/attach/2",
            mime_type="text/plain",
            size_bytes=500,
            attachment_id="10034",
        )
        result = enricher.enrich(make_defect(attachments=[att]))

        assert result.screenshots_analyzed == 0
        jira_reader.download_attachment.assert_not_called()

    def test_handles_download_failure_gracefully(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        jira_reader = MagicMock()
        jira_reader.download_attachment.side_effect = Exception("Connection timeout")

        enricher = DefectEnricher(ai_provider=provider, jira_reader=jira_reader)

        att = JiraAttachment(
            filename="screen.png",
            url="https://jira/attach/1",
            mime_type="image/png",
            size_bytes=1000,
            attachment_id="10033",
        )
        # Should not raise — just skip the screenshot
        result = enricher.enrich(make_defect(attachments=[att]))
        assert result.screenshots_analyzed == 0


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

class TestPromptBuilding:
    def test_prompt_contains_issue_key(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        enricher.enrich(make_defect(issue_key="STWA-99"))

        prompt = provider.complete.call_args.kwargs["prompt"]
        assert "STWA-99" in prompt

    def test_prompt_contains_description(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        enricher.enrich(make_defect(description="Kliknąłem Zapisz i wybuchło"))

        prompt = provider.complete.call_args.kwargs["prompt"]
        assert "Kliknąłem Zapisz i wybuchło" in prompt

    def test_prompt_contains_comments(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        comments = [JiraComment(author="Dev", body="Sprawdziłem logi", created="2026-06-10")]
        enricher.enrich(make_defect(comments=comments))

        prompt = provider.complete.call_args.kwargs["prompt"]
        assert "Sprawdziłem logi" in prompt

    def test_prompt_contains_issue_links(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        links = [JiraIssueLink(
            link_type="Blocks", direction="inward",
            related_issue_key="STWA-1", related_issue_summary="Login broken"
        )]
        enricher.enrich(make_defect(issue_links=links))

        prompt = provider.complete.call_args.kwargs["prompt"]
        assert "STWA-1" in prompt

    def test_screenshot_note_when_no_images(self):
        provider = make_mock_provider(SAMPLE_AI_RESPONSE)
        enricher = DefectEnricher(ai_provider=provider)

        enricher.enrich(make_defect())

        prompt = provider.complete.call_args.kwargs["prompt"]
        assert "None provided" in prompt
