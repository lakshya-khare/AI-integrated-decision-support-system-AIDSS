"""
Audit Trail & Controller Decision Governance Engine
Maintains an immutable operational audit log of all automated recommendations,
controller approvals, and manual overrides with justification.
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel

from backend.config import settings


class AuditRecord(BaseModel):
    audit_id: str
    timestamp: str
    controller_id: str
    event_type: str                   # "RECOMMENDATION_GENERATED", "DECISION_APPROVED", "DECISION_OVERRIDDEN", "DECISION_REJECTED"
    recommendation_id: Optional[str] = None
    train_number: str
    location: str
    action_taken: str
    override_reason: Optional[str] = None
    projected_delay_delta_mins: float = 0.0
    telemetry_snapshot: Dict[str, Any] = {}


class AuditTrailManager:
    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or settings.AUDIT_LOG_FILE
        self._records: List[AuditRecord] = []
        self._load()

    def _load(self):
        if self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = [AuditRecord(**r) for r in data]
            except Exception:
                self._records = []
        else:
            self._records = []
            self._save()

    def _save(self):
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump([r.model_dump() for r in self._records], f, indent=2)
        except Exception:
            pass

    def record_event(
        self,
        event_type: str,
        train_number: str,
        location: str,
        action_taken: str,
        controller_id: str = "WAT-SCOR-01",
        recommendation_id: Optional[str] = None,
        override_reason: Optional[str] = None,
        projected_delay_delta_mins: float = 0.0,
        telemetry: Optional[Dict[str, Any]] = None
    ) -> AuditRecord:
        record = AuditRecord(
            audit_id=f"AUD-{len(self._records) + 1:04d}",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            controller_id=controller_id,
            event_type=event_type,
            recommendation_id=recommendation_id,
            train_number=train_number,
            location=location,
            action_taken=action_taken,
            override_reason=override_reason,
            projected_delay_delta_mins=projected_delay_delta_mins,
            telemetry_snapshot=telemetry or {}
        )
        self._records.insert(0, record)
        self._save()
        return record

    def get_records(self, limit: int = 50) -> List[AuditRecord]:
        return self._records[:limit]
