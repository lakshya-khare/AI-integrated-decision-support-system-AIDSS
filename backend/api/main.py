"""
AIDSS Main Web API Server
FastAPI Application serving REST endpoints, What-If simulator, and Railway Controller Console.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.config import settings, BASE_DIR
from backend.adapters.sample_data_adapter import SampleDataAdapter
from backend.adapters.live_tms_adapter import LiveTMSAdapter
from backend.engine.network import NetworkEngine
from backend.engine.solver import RailwayScheduleOptimizer
from backend.engine.simulator import WhatIfSimulator, WhatIfScenarioRequest, WhatIfSimulationResult
from backend.engine.explainability import OperationalExplainabilityEngine
from backend.engine.audit import AuditTrailManager
from backend.engine.signalling import SignallingTelemetryEngine, SignalAspect, SectionThroughputMetrics
from backend.domain.models import ControllerDecision, SectionKPIs, TrainDirection

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Ministry of Railways Decision Support System for Section Throughput Maximization."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Core Services
sample_adapter = SampleDataAdapter()
live_tms_adapter = LiveTMSAdapter()

# Active adapter based on configuration
current_mode = settings.DATA_SOURCE_MODE
active_adapter = sample_adapter if current_mode == "sample" else live_tms_adapter

stations = active_adapter.get_corridor_stations()
block_sections = active_adapter.get_block_sections()

network_engine = NetworkEngine(stations, block_sections)
optimizer = RailwayScheduleOptimizer(stations, block_sections)
simulator = WhatIfSimulator(optimizer, network_engine)
audit_manager = AuditTrailManager()
signalling_engine = SignallingTelemetryEngine(stations, block_sections)

# Active recommendations cache
active_recommendations = []
active_trains_cache = []


def refresh_active_trains():
    global active_trains_cache, active_recommendations
    # Fetch active trains across the 24-hour corridor
    all_trains = active_adapter.get_active_trains(0, 86400)
    # Establish baseline conflict-free schedule and loop-hold recommendations
    optimized, recs = optimizer._solve_heuristic(all_trains[:80], blocked=set())
    active_trains_cache = optimized
    active_recommendations = recs


refresh_active_trains()


# API Models
class SwitchModeRequest(BaseModel):
    mode: str                         # "sample" or "live_tms"
    endpoint_url: Optional[str] = None
    api_key: Optional[str] = None


class DecisionActionRequest(BaseModel):
    recommendation_id: str
    action_taken: str                 # "APPROVED", "OVERRIDDEN", "REJECTED"
    controller_id: str = "WAT-SCOR-01"
    override_reason: Optional[str] = None


@app.get("/api/status")
def get_system_status():
    adapter_health = active_adapter.get_health_status()
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "mode": current_mode,
        "zone": settings.ZONE,
        "division": settings.DIVISION,
        "section": f"{settings.SECTION_CODE} ({settings.SECTION_NAME})",
        "corridor_length_km": settings.CORRIDOR_LENGTH_KM,
        "total_stations": len(stations),
        "active_trains_count": len(active_trains_cache),
        "adapter_health": adapter_health
    }


@app.post("/api/datasource/switch")
def switch_data_source(req: SwitchModeRequest):
    global current_mode, active_adapter
    if req.mode not in ["sample", "live_tms"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Choose 'sample' or 'live_tms'.")
    
    if req.mode == "live_tms":
        if req.endpoint_url:
            live_tms_adapter.endpoint_url = req.endpoint_url
        if req.api_key:
            live_tms_adapter.api_key = req.api_key
        live_tms_adapter._check_connection()
        active_adapter = live_tms_adapter
        current_mode = "live_tms"
    else:
        active_adapter = sample_adapter
        current_mode = "sample"

    refresh_active_trains()
    return {
        "status": "SUCCESS",
        "current_mode": current_mode,
        "adapter_health": active_adapter.get_health_status()
    }


@app.get("/api/infrastructure")
def get_infrastructure():
    return {
        "corridor": settings.SECTION_NAME,
        "length_km": settings.CORRIDOR_LENGTH_KM,
        "stations": [s.model_dump() for s in stations],
        "block_sections": [b.model_dump() for b in block_sections]
    }


@app.get("/api/trains/active")
def get_active_trains(limit: int = 100):
    return [t.model_dump() for t in active_trains_cache[:limit]]


@app.get("/api/trains/positions")
def get_train_realtime_positions(time_sec: int = Query(56700, ge=0, le=86400*2)):
    """
    Returns real-time train positions, track occupancies, and speeds at specified operational second.
    """
    positions = network_engine.get_realtime_positions(active_trains_cache, time_sec)
    return {
        "timestamp_sec": time_sec,
        "time_formatted": f"{String(time_sec // 3600 % 24) if False else f'{time_sec // 3600 % 24:02d}:{(time_sec % 3600) // 60:02d}:{time_sec % 60:02d} IST'}",
        "total_active_trains": len([p for p in positions if p.get("status") in ["RUNNING", "HALTED"]]),
        "positions": positions
    }


@app.get("/api/conflicts")
def get_conflicts():
    conflicts = network_engine.detect_conflicts(active_trains_cache)
    return [c.model_dump() for c in conflicts]


@app.get("/api/recommendations")
def get_recommendations(time_sec: Optional[int] = Query(None, ge=0, le=86400*2), lookahead_mins: int = 90):
    enriched = []
    sttn_map = {s.code: s for s in stations}
    train_map = {t.train_number: t for t in active_trains_cache}

    for rec in active_recommendations:
        t = train_map.get(rec.train_number)
        sttn = sttn_map.get(rec.station_code)
        if not t or not sttn:
            continue

        stop = next((s for s in t.stops if s.station_code == rec.station_code), None)
        t_arr = stop.actual_arrival if (stop and stop.actual_arrival is not None) else (rec.target_time_sec or (stop.scheduled_arrival if stop else 0))
        t_dep = stop.actual_departure if (stop and stop.actual_departure is not None) else (stop.scheduled_departure if stop else t_arr + 120)

        # Dynamic lifecycle check if operational time is provided
        if time_sec is not None:
            if rec.status == "PENDING":
                # If train has already passed/arrived without loop action, it is EXPIRED (too late)
                if time_sec > t_arr:
                    rec.status = "EXPIRED"
                    continue  # Prune expired recommendation from active controller feed

                # Check lookahead window (e.g. within 90 minutes)
                if t_arr - time_sec > lookahead_mins * 60:
                    continue  # Not yet in immediate operational lookahead

            elif rec.status == "APPROVED":
                # Approved recommendations remain visible while train is active/approaching/executing
                if time_sec > t_dep + 1800:
                    continue  # Cleared section > 30m ago

            elif rec.status in ["EXPIRED", "REJECTED"]:
                continue

        ov_train = train_map.get(rec.overtaking_train) if rec.overtaking_train else None
        details = OperationalExplainabilityEngine.enrich_recommendation(rec, t, sttn, overtaking_train=ov_train)

        # Append real-time countdown telemetry
        if time_sec is not None:
            mins_left = round((t_arr - time_sec) / 60, 1)
            details["mins_until_arrival"] = max(0.0, mins_left)
            if mins_left <= 15:
                details["urgency"] = "CRITICAL (PASSING IN SECTION)"
            elif mins_left <= 45:
                details["urgency"] = "APPROACHING"
            else:
                details["urgency"] = "SCHEDULED"

        enriched.append(details)

    return enriched


@app.post("/api/decisions/action")
def submit_decision(req: DecisionActionRequest):
    global active_recommendations, active_trains_cache
    target_rec = next((r for r in active_recommendations if r.recommendation_id == req.recommendation_id), None)
    
    if not target_rec:
        raise HTTPException(status_code=404, detail="Recommendation ID not found.")

    target_rec.status = req.action_taken
    train_map = {t.train_number: t for t in active_trains_cache}
    target_train = train_map.get(target_rec.train_number)

    if req.action_taken == "APPROVED" and target_train:
        # 1. Mutate target train's schedule at this station to divert onto Loop Line
        target_stop = next((s for s in target_train.stops if s.station_code == target_rec.station_code), None)
        if target_stop:
            target_stop.assigned_line = str(target_rec.target_line)
            min_dwell = 120 if target_stop.is_commercial_halt else 0
            base_arr = target_stop.actual_arrival or target_stop.scheduled_arrival
            target_stop.actual_arrival = base_arr
            target_stop.actual_departure = base_arr + min_dwell + target_rec.hold_duration_sec
            target_stop.delay_departure_mins = round((target_stop.actual_departure - target_stop.scheduled_departure) / 60, 1)

            # Propagate delay shift downstream for subsequent stops
            stop_idx = target_train.stops.index(target_stop)
            for j in range(stop_idx + 1, len(target_train.stops)):
                curr_s = target_train.stops[j]
                prev_s = target_train.stops[j - 1]
                run_time = max(180, curr_s.scheduled_arrival - prev_s.scheduled_departure)
                curr_s.actual_arrival = prev_s.actual_departure + run_time
                curr_dwell = 120 if curr_s.is_commercial_halt else 0
                curr_s.actual_departure = curr_s.actual_arrival + curr_dwell
                curr_s.delay_arrival_mins = round((curr_s.actual_arrival - curr_s.scheduled_arrival) / 60, 1)
                curr_s.delay_departure_mins = round((curr_s.actual_departure - curr_s.scheduled_departure) / 60, 1)

        # 2. Grant clear Main Line green aspect to overtaking train
        if target_rec.overtaking_train:
            ov_train = train_map.get(target_rec.overtaking_train)
            if ov_train:
                ov_stop = next((s for s in ov_train.stops if s.station_code == target_rec.station_code), None)
                if ov_stop:
                    ov_stop.assigned_line = "2" if ov_train.direction == TrainDirection.UP else "3"
                    # Overtaking train saves delay because freight is held on loop
                    savings_sec = int(target_rec.projected_delay_savings_mins * 60)
                    ov_idx = ov_train.stops.index(ov_stop)
                    for k in range(ov_idx, len(ov_train.stops)):
                        s = ov_train.stops[k]
                        if s.actual_arrival:
                            s.actual_arrival = max(s.scheduled_arrival, s.actual_arrival - savings_sec)
                        if s.actual_departure:
                            s.actual_departure = max(s.scheduled_departure, s.actual_departure - savings_sec)
                        s.delay_arrival_mins = max(0.0, round((s.actual_arrival - s.scheduled_arrival) / 60, 1))
                        s.delay_departure_mins = max(0.0, round((s.actual_departure - s.scheduled_departure) / 60, 1))

    # Audit log entry
    audit_rec = audit_manager.record_event(
        event_type=f"DECISION_{req.action_taken}",
        train_number=target_rec.train_number,
        location=target_rec.station_code,
        action_taken=target_rec.action.value,
        controller_id=req.controller_id,
        recommendation_id=target_rec.recommendation_id,
        override_reason=req.override_reason,
        projected_delay_delta_mins=target_rec.projected_delay_savings_mins if req.action_taken == "APPROVED" else 0.0,
        telemetry={"train_name": target_rec.train_name, "station": target_rec.station_code}
    )

    # Propagate to Field / Live TMS
    decision_obj = ControllerDecision(
        decision_id=audit_rec.audit_id,
        recommendation_id=target_rec.recommendation_id,
        controller_id=req.controller_id,
        action_taken=req.action_taken,
        override_reason=req.override_reason,
        timestamp=audit_rec.timestamp
    )
    active_adapter.submit_controller_decision(decision_obj)

    # Compute updated live KPIs
    live_kpis = simulator._calculate_kpis(active_trains_cache).model_dump()

    return {
        "status": "RECORDED",
        "action_taken": req.action_taken,
        "decision": decision_obj.model_dump(),
        "audit_id": audit_rec.audit_id,
        "updated_kpis": live_kpis
    }


@app.post("/api/optimize")
def trigger_reoptimization():
    global active_trains_cache, active_recommendations
    optimized, recs = optimizer.optimize(active_trains_cache, time_limit_sec=3)
    active_trains_cache = optimized
    active_recommendations = recs
    return {
        "status": "OPTIMIZED",
        "trains_recalculated": len(optimized),
        "recommendations_count": len(recs),
        "kpis": simulator._calculate_kpis(optimized).model_dump()
    }


@app.post("/api/simulate")
def run_what_if_simulation(req: WhatIfScenarioRequest):
    result = simulator.run_simulation(active_trains_cache, req)
    return result.model_dump()


@app.get("/api/kpis")
def get_kpis(time_sec: Optional[int] = None):
    kpis = simulator._calculate_kpis(active_trains_cache, time_sec=time_sec)
    kpi_dict = kpis.model_dump()
    approved_recs = [r for r in active_recommendations if r.status == "APPROVED"]
    kpi_dict["conflicts_resolved_count"] = len(approved_recs)
    kpi_dict["total_delay_saved_mins"] = round(sum(r.projected_delay_savings_mins for r in approved_recs), 1)
    return kpi_dict


@app.get("/api/audit")
def get_audit_trail(limit: int = 50):
    records = audit_manager.get_records(limit)
    return [r.model_dump() for r in records]


@app.get("/api/signalling/aspects")
def get_signal_aspects(time_sec: Optional[int] = None):
    t_sec = time_sec if time_sec is not None else 56700
    signals = signalling_engine.get_live_signals(active_trains_cache, current_time_sec=t_sec)
    return [s.model_dump() for s in signals]


@app.get("/api/analytics/capacity")
def get_capacity_analytics():
    metrics = signalling_engine.compute_scotts_capacity(len(active_trains_cache))
    return metrics.model_dump()


# Serve Frontend
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(frontend_dir / "index.html")
