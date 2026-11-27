"""
What-If Scenario Simulation & Counterfactual Evaluation Engine
Allows Section Controllers to evaluate the operational impact of disruptions and interventions.
"""

import time
import copy
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from backend.domain.models import Train, Station, BlockSection, SectionKPIs, DispatchRecommendation
from backend.engine.solver import RailwayScheduleOptimizer
from backend.engine.network import NetworkEngine


class ScenarioCondition(BaseModel):
    condition_id: str = "C1"
    enabled: bool = True
    condition_type: str        # "TRAIN_DELAY", "TRACK_BLOCK", "SPEED_RESTRICTION"
    target_train_no: Optional[str] = None
    target_station: Optional[str] = None
    target_block_id: Optional[str] = None
    delay_minutes: float = 0.0
    speed_restriction_kmh: Optional[int] = 30
    description: Optional[str] = None


class WhatIfScenarioRequest(BaseModel):
    scenario_name: str
    scenario_type: Optional[str] = "COMPOUND"
    conditions: List[ScenarioCondition] = Field(default_factory=list)
    # Legacy single-condition backwards compatibility
    target_train_no: Optional[str] = None
    target_station: Optional[str] = None
    target_block_id: Optional[str] = None
    delay_minutes: float = 0.0
    speed_restriction_kmh: Optional[int] = None
    holding_station: Optional[str] = None


class WhatIfSimulationResult(BaseModel):
    scenario_name: str
    scenario_type: str
    applied_conditions: List[str] = Field(default_factory=list)
    baseline_kpis: SectionKPIs
    scenario_kpis: SectionKPIs
    kpi_delta: Dict[str, Any]
    impact_summary: str
    train_diffs: List[Dict[str, Any]] = Field(default_factory=list)
    new_recommendations: List[DispatchRecommendation]
    simulated_trains: List[Train]


class WhatIfSimulator:
    def __init__(self, optimizer: RailwayScheduleOptimizer, network: NetworkEngine):
        self.optimizer = optimizer
        self.network = network

    def run_simulation(
        self,
        base_trains: List[Train],
        scenario: WhatIfScenarioRequest
    ) -> WhatIfSimulationResult:
        """
        Executes counterfactual simulation across 1 or 2+ compound conditions.
        Produces side-by-side comparative analysis and train-by-train schedule delta.
        """
        # 1. Compute Baseline KPIs
        baseline_kpis = self._calculate_kpis(base_trains)

        # 2. Build normalized condition list
        conditions = list(scenario.conditions)
        if not conditions:
            # Fall back to top-level legacy fields
            stype = scenario.scenario_type or "TRAIN_DELAY"
            conditions.append(ScenarioCondition(
                condition_id="C1",
                enabled=True,
                condition_type=stype,
                target_train_no=scenario.target_train_no,
                target_station=scenario.target_station,
                target_block_id=scenario.target_block_id,
                delay_minutes=scenario.delay_minutes,
                speed_restriction_kmh=scenario.speed_restriction_kmh
            ))

        # 3. Clone trains and apply each active condition
        sim_trains = [t.model_copy(deep=True) for t in base_trains]
        blocked_sections = []
        applied_descs = []

        for cond in conditions:
            if not cond.enabled:
                continue

            if cond.condition_type == "TRAIN_DELAY" and cond.target_train_no:
                delay_sec = int(cond.delay_minutes * 60)
                target = next((t for t in sim_trains if t.train_number == cond.target_train_no), None)
                if target:
                    found_sttn = False
                    for stop in target.stops:
                        if cond.target_station is None or stop.station_code == cond.target_station:
                            found_sttn = True
                        if found_sttn:
                            stop.scheduled_arrival += delay_sec
                            stop.scheduled_departure += delay_sec
                            stop.actual_arrival = (stop.actual_arrival or stop.scheduled_arrival) + delay_sec
                            stop.actual_departure = (stop.actual_departure or stop.scheduled_departure) + delay_sec
                            stop.delay_arrival_mins += cond.delay_minutes
                    applied_descs.append(f"Train {cond.target_train_no} delayed +{cond.delay_minutes:.0f}m at {cond.target_station or 'origin'}")

            elif cond.condition_type == "TRACK_BLOCK" and cond.target_block_id:
                blocked_sections.append(cond.target_block_id)
                b_parts = cond.target_block_id.split("-")
                if len(b_parts) == 2:
                    s1, s2 = b_parts[0], b_parts[1]
                    for t in sim_trains:
                        for stop in t.stops:
                            if stop.station_code in [s1, s2]:
                                stop.actual_arrival = (stop.actual_arrival or stop.scheduled_arrival) + 600
                                stop.actual_departure = (stop.actual_departure or stop.scheduled_departure) + 600
                applied_descs.append(f"Track block on {cond.target_block_id} (Single-line pilot working +10m)")

            elif cond.condition_type == "SPEED_RESTRICTION" and cond.speed_restriction_kmh:
                spd = cond.speed_restriction_kmh
                for t in sim_trains:
                    if t.max_speed_kmh > spd:
                        t.max_speed_kmh = spd
                        for stop in t.stops:
                            if cond.target_station and stop.station_code == cond.target_station:
                                stop.actual_arrival = (stop.actual_arrival or stop.scheduled_arrival) + 420
                                stop.actual_departure = (stop.actual_departure or stop.scheduled_departure) + 420
                applied_descs.append(f"TSR caution order: {spd} km/h restriction at {cond.target_station or 'corridor'}")

        # 4. Re-optimize under scenario constraints
        optimized_sim_trains, recommendations = self.optimizer.optimize(
            sim_trains, time_limit_sec=4, blocked_sections=blocked_sections
        )

        # 5. Compute Scenario KPIs
        scenario_kpis = self._calculate_kpis(optimized_sim_trains)

        # 6. Formulate Train-by-Train Comparative Delta List
        train_diffs = []
        base_map = {t.train_number: t for t in base_trains}
        for sim_t in optimized_sim_trains:
            base_t = base_map.get(sim_t.train_number)
            if not base_t or not base_t.stops or not sim_t.stops:
                continue
            base_last = base_t.stops[-1].actual_arrival or base_t.stops[-1].scheduled_arrival
            sim_last = sim_t.stops[-1].actual_arrival or sim_t.stops[-1].scheduled_arrival
            diff_mins = round((sim_last - base_last) / 60, 1)

            # Include affected trains or targeted trains
            is_target = any(c.target_train_no == sim_t.train_number for c in conditions)
            if abs(diff_mins) >= 0.5 or is_target:
                b_hrs = (base_last // 3600) % 24
                b_mins = (base_last % 3600) // 60
                s_hrs = (sim_last // 3600) % 24
                s_mins = (sim_last % 3600) // 60

                status_label = "SEVERELY DELAYED" if diff_mins >= 15 else (
                    "MODERATELY DELAYED" if diff_mins >= 5 else (
                        "REGULATED" if diff_mins > 0 else "ON SCHEDULE"
                    )
                )

                train_diffs.append({
                    "train_number": sim_t.train_number,
                    "train_name": sim_t.name,
                    "priority": sim_t.priority.value,
                    "direction": sim_t.direction.value,
                    "baseline_arrival": f"{b_hrs:02d}:{b_mins:02d}",
                    "simulated_arrival": f"{s_hrs:02d}:{s_mins:02d}",
                    "delay_delta_mins": diff_mins,
                    "status": status_label
                })

        train_diffs.sort(key=lambda x: -x["delay_delta_mins"])

        # 7. Formulate KPI Delta and Impact Summary
        delta = {
            "delay_change_mins": round(scenario_kpis.average_delay_minutes - baseline_kpis.average_delay_minutes, 1),
            "punctuality_change_percent": round(scenario_kpis.punctuality_rate_percent - baseline_kpis.punctuality_rate_percent, 1),
            "throughput_change": scenario_kpis.throughput_trains_24h - baseline_kpis.throughput_trains_24h,
            "conflicts_mitigated": len(recommendations)
        }

        cond_summary = " + ".join(applied_descs) if applied_descs else scenario.scenario_name
        impact_text = (
            f"Compound Scenario [{cond_summary}]: "
            f"Average corridor delay shifts by {delta['delay_change_mins']:+} min/train; "
            f"Punctuality index projected at {scenario_kpis.punctuality_rate_percent}% "
            f"({delta['punctuality_change_percent']:+}%). "
            f"A total of {len(train_diffs)} trains directly affected. "
            f"AI solver generated {len(recommendations)} dynamic loop/holding interventions to maintain section throughput."
        )

        return WhatIfSimulationResult(
            scenario_name=scenario.scenario_name,
            scenario_type=scenario.scenario_type or "COMPOUND",
            applied_conditions=applied_descs,
            baseline_kpis=baseline_kpis,
            scenario_kpis=scenario_kpis,
            kpi_delta=delta,
            impact_summary=impact_text,
            train_diffs=train_diffs,
            new_recommendations=recommendations,
            simulated_trains=optimized_sim_trains
        )

    def _calculate_kpis(self, trains: List[Train], time_sec: Optional[int] = None) -> SectionKPIs:
        total_delays = []
        on_time_count = 0
        total_stops = 0
        active_now = 0

        for t in trains:
            if not t.stops:
                continue

            t_start = t.stops[0].actual_departure or t.stops[0].scheduled_departure
            t_end = t.stops[-1].actual_arrival or t.stops[-1].scheduled_arrival
            if time_sec is not None and t_start <= time_sec <= t_end:
                active_now += 1

            for s in t.stops:
                total_stops += 1
                arr_delay = s.delay_arrival_mins
                total_delays.append(max(0.0, arr_delay))
                if arr_delay <= 5.0:  # Indian Railways on-time standard (+-5 mins)
                    on_time_count += 1

        avg_delay = round(sum(total_delays) / max(len(total_delays), 1), 1)
        punctuality = round((on_time_count / max(total_stops, 1)) * 100, 1)

        # Section Throughput based on full day trains
        throughput = len(trains)

        return SectionKPIs(
            throughput_trains_24h=throughput,
            active_trains_on_section=active_now if time_sec is not None else len(trains),
            average_delay_minutes=avg_delay,
            punctuality_rate_percent=punctuality,
            track_utilization_percent=min(96.0, round(52.0 + (len(trains) * 0.18), 1)),
            conflicts_resolved_count=0
        )
