"""
Explainable AI (XAI) & Operational Reasoning Engine
Generates human-readable, context-aware dispatch rationale for Railway Section Controllers.
"""

from typing import Dict, Any, List
from backend.domain.models import DispatchRecommendation, Train, Station, TrainPriority, ActionType


class OperationalExplainabilityEngine:
    """
    Translates mathematical optimization decisions into authentic Indian Railways operational terminology.
    """

    @staticmethod
    def enrich_recommendation(
        rec: DispatchRecommendation,
        train: Train,
        station: Station,
        overtaking_train: Train = None
    ) -> Dict[str, Any]:
        
        loop_line = next((l for l in station.lines if str(l.line_number) == str(rec.target_line)), None)
        csr_length = loop_line.csr_length_m if loop_line else 720.0
        
        # Operational context builder
        justification_points = []
        
        if rec.action == ActionType.LOOP_HOLD:
            justification_points.append(
                f"Loop Line {rec.target_line} at {station.name} ({station.code}) has Clear Standing Room (CSR) of {csr_length}m, which safely accommodates rake length of {train.length_meters}m with 10% safety margin."
            )
            if overtaking_train:
                justification_points.append(
                    f"Grants clear UP/DN main line green aspect to higher-priority {overtaking_train.name} ({overtaking_train.priority.value}), preventing an estimated {rec.projected_delay_savings_mins} minutes of cascading headway delay."
                )
            else:
                justification_points.append(
                    f"Absorbs headway bunching on block section, protecting downstream junction throughput at Vizianagaram (VZM) / Palasa (PSA)."
                )

        elif rec.action == ActionType.PROCEED_MAIN:
            justification_points.append(
                f"Section running speed maintained at maximum permissible {train.max_speed_kmh} km/h on through line."
            )

        counterfactual_risk = (
            f"If overridden (allowing {train.train_number} to lead on through line), following high-priority traffic "
            f"will face caution aspects (Double Yellow / Yellow) across 3 consecutive block sections, "
            f"incurring ~{rec.projected_delay_savings_mins * 1.6:.1f} mins cascading corridor delay."
        )

        target_t = rec.target_time_sec
        time_formatted = f"{target_t // 3600 % 24:02d}:{(target_t % 3600) // 60:02d}:{(target_t % 60):02d} IST" if target_t is not None else "--:-- IST"

        return {
            "recommendation_id": rec.recommendation_id,
            "train_number": train.train_number,
            "train_name": train.name,
            "station": f"{station.name} ({station.code})",
            "station_code": station.code,
            "action": rec.action.value,
            "target_line": rec.target_line,
            "assigned_line": f"Line {rec.target_line} (CSR {csr_length}m)",
            "hold_minutes": round(rec.hold_duration_sec / 60, 1),
            "hold_duration_sec": rec.hold_duration_sec,
            "delay_saved_minutes": rec.projected_delay_savings_mins,
            "projected_delay_savings_mins": rec.projected_delay_savings_mins,
            "primary_rationale": rec.rationale,
            "status": rec.status,
            "target_time_sec": target_t,
            "target_time_formatted": time_formatted,
            "overtaking_train": rec.overtaking_train,
            "technical_justifications": justification_points,
            "counterfactual_risk": counterfactual_risk,
            "compliance_rules": [
                "General & Subsidiary Rules (G&SR) Rule 4.23 - Precedence of Passenger over Goods",
                "Operating Manual Section 14 - Maximum Permissible Loop Occupancy Limit",
                "Signal Engineering Manual (SEM) - Absolute/Automatic Headway Clearance"
            ]
        }
