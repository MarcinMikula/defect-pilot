"""
run_retest.py — generate a Playwright retest script for a Jira issue.

Usage:
    python scripts/run_retest.py --issue STWA-9
    python scripts/run_retest.py --issue STWA-9 --url https://...
    python scripts/run_retest.py --issue STWA-9 --debug
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="defect-pilot — Playwright retest generator")
    parser.add_argument("--issue", required=True, help="Jira issue key, e.g. STWA-9")
    parser.add_argument("--url", help="Override record URL (if bug report URL is stale)")
    parser.add_argument("--debug", action="store_true", help="Show enrichment details")
    parser.add_argument("--dry-run", action="store_true", help="Print script to stdout, don't save")
    args = parser.parse_args()

    print(f"\n🎭  defect-pilot — generating retest for {args.issue}\n")

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    from config.settings import Settings
    settings = Settings()
    print(f"✅ Config loaded — AI provider: {settings.ai_provider}")

    # ------------------------------------------------------------------
    # Jira
    # ------------------------------------------------------------------
    from agent.jira_reader import JiraReader
    reader = JiraReader(
        base_url=settings.jira_base_url,
        email=settings.jira_email,
        api_token=settings.jira_api_token,
    )

    print("📡 Checking Jira connection...")
    if not reader.check_connection():
        print("❌ Jira connection failed — check .env credentials")
        sys.exit(1)
    print("✅ Jira connected\n")

    print(f"📥 Fetching {args.issue}...")
    defect = reader.get_defect(args.issue)
    print(f"✅ Fetched: '{defect.summary}'")
    print(f"   Type:    {defect.issue_type}")

    # ------------------------------------------------------------------
    # Issue type guard
    # ------------------------------------------------------------------
    supported_raw = os.getenv("SUPPORTED_ISSUE_TYPES", "bug,błąd,defect,error,problem")
    supported = {t.strip().lower() for t in supported_raw.split(",")}
    if defect.issue_type.lower() not in supported:
        print(
            f"\n⚠️  Issue type '{defect.issue_type}' is not supported.\n"
            f"   defect-pilot generates retests for bugs only.\n"
            f"   Supported types: {supported_raw}\n"
            f"   Override via SUPPORTED_ISSUE_TYPES in .env\n"
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # AI enrichment
    # ------------------------------------------------------------------
    from ai.provider_factory import create_provider
    from agent.defect_enricher import DefectEnricher

    print(f"\n🤖 Initializing AI provider: {settings.ai_provider}...")
    ai = create_provider(settings)
    print("✅ Provider ready\n")

    print("🔍 Enriching defect with AI...")
    enricher = DefectEnricher(ai_provider=ai, jira_reader=reader)
    enriched = enricher.enrich(defect)
    print(f"✅ Enriched — completeness: {enriched.completeness_score}/100")

    # URL override from CLI
    if args.url:
        print(f"🔗 URL override: {args.url}")
        enriched.url = args.url

    if args.debug:
        print(f"\n   Steps:    {len(enriched.steps_to_reproduce)}")
        print(f"   URL:      {enriched.url or '(not extracted)'}")
        print(f"   Elements: {len(enriched.ui_elements)}")
        print(f"   Missing:  {enriched.missing_info}")

    # ------------------------------------------------------------------
    # Generate script
    # ------------------------------------------------------------------
    from retest.playwright_writer import PlaywrightWriter

    print("\n🎭 Generating Playwright retest script...")
    writer = PlaywrightWriter()

    if args.dry_run:
        script = writer.generate(enriched)
        print("\n" + "=" * 60)
        print(script)
        print("=" * 60)
        print("\n(dry-run — script not saved)")
    else:
        path = writer.save(enriched)
        print(f"✅ Script saved: {path}")
        print(f"\n▶️  Run with:")
        print(f"   pytest {path} -v")
        print(f"\n⚠️  Before running:")
        print(f"   1. Review TODO comments in the script")
        print(f"   2. Verify selectors manually")
        print(f"   3. Check test data requirements at top of file")

    print(f"\n✅ Done — {args.issue}\n")


if __name__ == "__main__":
    main()