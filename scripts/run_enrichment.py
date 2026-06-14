"""
defect-pilot — live enrichment runner.
Fetches a Jira issue, enriches it with AI, and prints structured results.

Usage:
    python scripts/run_enrichment.py --issue STWA-9
    python scripts/run_enrichment.py --issue STWA-5 --debug
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config.settings import load_config
from agent.jira_reader import JiraReader
from agent.defect_enricher import DefectEnricher
from ai.provider_factory import get_provider


def parse_args():
    parser = argparse.ArgumentParser(
        description="defect-pilot — AI-powered Jira defect enrichment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python scripts/run_enrichment.py --issue STWA-9
  python scripts/run_enrichment.py --issue STWA-9 --debug
        """
    )
    parser.add_argument(
        "--issue", "-i",
        required=True,
        help="Jira issue key (e.g. STWA-9, PROJ-123)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print raw AI response for debugging"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    print(f"\n🛩️  defect-pilot — enriching {args.issue}\n")

    config = load_config()
    print(f"✅ Config loaded — AI provider: {config.ai.provider}")

    reader = JiraReader(
        base_url=config.jira.base_url,
        email=config.jira.email,
        api_token=config.jira.api_token,
    )

    print("\n📡 Checking Jira connection...")
    if not reader.check_connection():
        print("❌ Jira connection failed — check .env credentials")
        sys.exit(1)
    print("✅ Jira connected")

    print(f"\n📥 Fetching {args.issue}...")
    defect = reader.get_defect(args.issue)
    print(f"✅ Fetched: '{defect.summary}'")
    print(f"   Status:      {defect.status}")
    print(f"   Type:        {defect.issue_type}")
    print(f"   Priority:    {defect.priority}")
    print(f"   Attachments: {len(defect.attachments)}")
    print(f"   Comments:    {len(defect.comments)}")
    print(f"   Links:       {len(defect.issue_links)}")
    if defect.description:
        print(f"   Description: {defect.description[:120]}...")
    else:
        print("   Description: (empty)")

    if defect.attachments:
        print("\n📎 Attachments:")
        for att in defect.attachments:
            print(f"   - {att.filename} ({att.mime_type}, {att.size_bytes} bytes)")

    print(f"\n🤖 Initializing AI provider: {config.ai.provider}...")
    provider = get_provider(config.ai)
    print("✅ Provider ready")

    print("\n🔍 Enriching defect with AI...")
    enricher = DefectEnricher(ai_provider=provider, jira_reader=reader)
    enriched = enricher.enrich(defect)

    print("\n" + "="*60)
    print(f"📊 ENRICHMENT RESULTS — {args.issue}")
    print("="*60)

    print(f"\n🎯 Completeness score: {enriched.completeness_score}/100")

    print(f"\n📋 Steps to reproduce ({len(enriched.steps_to_reproduce)}):")
    for i, step in enumerate(enriched.steps_to_reproduce, 1):
        print(f"   {i}. {step}")

    print(f"\n✅ Expected:\n   {enriched.expected_result or '(not extracted)'}")
    print(f"\n❌ Actual:\n   {enriched.actual_result or '(not extracted)'}")

    if enriched.url:
        print(f"\n🔗 URL: {enriched.url}")

    if enriched.ui_elements:
        print(f"\n🖱️  UI elements:")
        for el in enriched.ui_elements:
            print(f"   - {el}")

    if enriched.error_message:
        print(f"\n⚠️  Error message: {enriched.error_message}")

    if enriched.requirement_refs:
        print(f"\n📌 Requirement refs: {', '.join(enriched.requirement_refs)}")

    if enriched.missing_info:
        print(f"\n❓ Missing info:")
        for m in enriched.missing_info:
            print(f"   - {m}")

    print(f"\n📸 Screenshots analyzed: {enriched.screenshots_analyzed}")

    if args.debug:
        print("\n" + "="*60)
        print("🔬 RAW AI RESPONSE (--debug)")
        print("="*60)
        print(enriched.raw_ai_response)

    print("\n" + "="*60)
    print(f"✅ Done — {args.issue}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
