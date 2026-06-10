"""
[DOMAIN: GENERIC]
Defect Store — local SQLite database for tracking defect status.
Sprint 4 implementation target.
"""

import logging
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class DefectStatus(str, Enum):
    FETCHED = "fetched"
    ENRICHED = "enriched"
    SCRIPT_GENERATED = "script_generated"
    RETEST_PASSED = "retest_passed"
    RETEST_FAILED = "retest_failed"
    JIRA_UPDATED = "jira_updated"


class DefectStore:
    """
    Local SQLite store for defect lifecycle tracking.

    Tracks: issue_key, status, timestamps, enriched data, script path.

    TODO Sprint 4:
    - SQLAlchemy models
    - CRUD operations
    - Status transition history
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"[DefectStore] Initialized at {db_path} (stub)")

    def save(self, issue_key: str, status: DefectStatus, **kwargs) -> None:
        """Save or update defect record."""
        logger.info(f"[DefectStore] Saving {issue_key} -> {status} (stub)")
        raise NotImplementedError("DefectStore.save — Sprint 4")

    def get(self, issue_key: str) -> dict | None:
        """Get defect record by issue key."""
        logger.info(f"[DefectStore] Getting {issue_key} (stub)")
        raise NotImplementedError("DefectStore.get — Sprint 4")
