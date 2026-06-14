"""
Live integration test — STWA-5
Runs against real Jira instance and real AI provider.
Usage: python scripts/test_live_stwa5.py
"""

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def main():
    print("\n🛩️  defect-pilot — live test on STWA-5\n")

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

    print("\n📥 Fetching STWA-5...")
    defect = reader.get_defect("STWA-5")
    print(f"✅ Fetched: '{defect.summary}'")
    print(f"   Status:      {defect.status}")
    print(f"   Type:        {defect.issue_type}")
    print(f"   Attachments: {len(defect.attachments)}")
    print(f"   Comments:    {len(defect.comments)}")
    if defect.description:
        print(f"   Description: {defect.description[:120]}...")
    else:
        print("   Description: (empty)")

    if defect.attachments:
        print("\n📎 Attachments:")
        for att in defect.attachments:
            print(f"   - {att.filename} ({att.mime_type}, {att.size_bytes} bytes, id={att.attachment_id})")

    print(f"\n🤖 Initializing AI provider: {config.ai.provider}...")
    provider = get_provider(config.ai)
    print("✅ Provider ready")

    print("\n🔍 Enriching defect with AI...")
    enricher = DefectEnricher(ai_provider=provider, jira_reader=reader)
    enriched = enricher.enrich(defect)

    print("\n" + "="*60)
    print("📊 ENRICHMENT RESULTS")
    print("="*60)

    print(f"\n🎯 Completeness score: {enriched.completeness_score}/100")

    print(f"\n📋 Steps to reproduce ({len(enriched.steps_to_reproduce)}):")
    for i, step in enumerate(enriched.steps_to_reproduce, 1):
        print(f"   {i}. {step}")

    print(f"\n✅ Expected:\n   {enriched.expected_result}")
    print(f"\n❌ Actual:\n   {enriched.actual_result}")

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
    print("\n" + "="*60)
    print("🔍 RAW AI RESPONSE (debug)")
    print("="*60)
    print(enriched.raw_ai_response)
    print("✅ Sprint 2 live test complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
