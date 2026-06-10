"""
[DOMAIN: GENERIC]
defect-pilot CLI entry point.
Sprint 5 target: full CLI with argparse.

Usage (Sprint 5):
    python -m defect_pilot --issue PROJ-123
    python -m defect_pilot --issue PROJ-123 --dry-run
    python -m defect_pilot --issue PROJ-123 --provider ollama
"""

import logging
import sys


def main():
    print("🛩️  defect-pilot")
    print("   Sprint 0 — scaffold complete.")
    print("   Sprint 1 (Jira Reader) coming next.")
    print()
    print("   Run with: python -m defect_pilot --issue PROJ-123")
    sys.exit(0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
