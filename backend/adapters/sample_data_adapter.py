"""
Sample Data Adapter (Waltair Division ECoR Digital Twin)
Parses infrastructure and timetables from KTV-PSA dataset and provides fast in-memory query access.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

from backend.config import settings, SAMPLE_DATA_DIR
from backend.domain.models import (
    Station, StationLine, LineType, BlockSection, Train,
    ScheduleStop, TrainPriority, TrainDirection, ControllerDecision
)
from backend.adapters.base import BaseDataSource

logger = logging.getLogger("aidss.adapter.sample")
logging.basicConfig(level=logging.INFO)

CACHE_FILE = SAMPLE_DATA_DIR / "ktv_psa_corridor_cache.json"


class SampleDataAdapter(BaseDataSource):
    """
    Offline Digital Twin Adapter for KTV-PSA Corridor.
    Loads real East Coast Railway topology, loop lines, passenger schedules, and freight rakes.
    """

    def __init__(self):
        self._stations: List[Station] = []
        self._station_map: Dict[str, Station] = {}
        self._block_sections: List[BlockSection] = []
        self._trains: List[Train] = []
        self._train_map: Dict[str, Train] = {}
        self._is_loaded = False
        self._initialize()

    def _initialize(self):
        if CACHE_FILE.exists():
            try:
                self._load_from_cache()
                self._is_loaded = True
                logger.info(f"Loaded {len(self._stations)} stations and {len(self._trains)} trains from cache.")
                return
            except Exception as e:
                logger.warning(f"Cache read error: {e}. Rebuilding from raw Excel files...")

        self._build_from_excel()
        self._save_to_cache()
        self._is_loaded = True

    def _build_from_excel(self):
        logger.info("Parsing raw Excel files from Sample Data directory...")
        
        # 1. Parse Route & Stations
        route_path = SAMPLE_DATA_DIR / "RouteSttnInfo.xlsx"
        df_route = pd.read_excel(route_path, sheet_name="KTV-PSA")
        
        # 2. Parse Station Lines & Infrastructure
        infra_path = SAMPLE_DATA_DIR / "KTV-PSA-Infra.xlsx"
        df_lines = pd.read_excel(infra_path, sheet_name="STTNLINE")
        df_blocks = pd.read_excel(infra_path, sheet_name="BLOCKSCTN")
        
        # Build Station Line index
        station_lines_dict: Dict[str, List[StationLine]] = {}
        for _, row in df_lines.iterrows():
            sttn = str(row.get("MAVSTTNCODE", "")).strip().upper()
            line_no = str(row.get("MAVLINENUMB", "1")).strip()
            line_type_str = str(row.get("MAVLINETYPE", "RL")).strip().upper()
            line_speed = int(row.get("MANLINESPEED", 15)) if pd.notna(row.get("MANLINESPEED")) else 15
            csr = float(row.get("MANCSR", 720)) if pd.notna(row.get("MANCSR")) else 720.0
            has_pf = str(row.get("MACPLATFORM", "N")).strip().upper() == "Y"
            
            line_type = LineType.MAIN if line_speed >= 80 else LineType.LOOP
            
            sline = StationLine(
                station_code=sttn,
                line_number=line_no,
                line_type=line_type,
                csr_length_m=csr,
                speed_limit_kmh=line_speed,
                has_platform=has_pf,
                is_electrified=True
            )
            station_lines_dict.setdefault(sttn, []).append(sline)

        # Build Stations List
        self._stations = []
        for _, row in df_route.iterrows():
            code = str(row["STATION_CODE"]).strip().upper()
            name = str(row["STATION_NAME"]).strip()
            seq = int(row["SEQ_NO"])
            cum_dist = float(row["DSPL_CUM_DIST"])
            avg_dist = float(row["AVGDISTANCE"]) if pd.notna(row["AVGDISTANCE"]) else 0.0
            is_junc = str(row.get("JUNC_FLAG", "N")).strip().upper() == "Y"
            is_cabin = str(row.get("CABIN_FLAG", "N")).strip().upper() == "Y"
            
            lines = station_lines_dict.get(code, [])
            if not lines:
                # Default standard 4-track station (2 main + 2 loops) if not explicitly in table
                lines = [
                    StationLine(station_code=code, line_number="1", line_type=LineType.LOOP, csr_length_m=720, speed_limit_kmh=15, has_platform=True),
                    StationLine(station_code=code, line_number="2", line_type=LineType.MAIN, csr_length_m=750, speed_limit_kmh=110, has_platform=True),
                    StationLine(station_code=code, line_number="3", line_type=LineType.MAIN, csr_length_m=750, speed_limit_kmh=110, has_platform=True),
                    StationLine(station_code=code, line_number="4", line_type=LineType.LOOP, csr_length_m=720, speed_limit_kmh=15, has_platform=False),
                ]
            
            sttn_obj = Station(
                sequence=seq,
                code=code,
                name=name,
                chainage_km=round(cum_dist, 2),
                inter_distance_km=round(avg_dist, 2),
                is_junction=is_junc,
                is_cabin=is_cabin,
                total_lines=len(lines),
                lines=lines
            )
            self._stations.append(sttn_obj)
            self._station_map[code] = sttn_obj

        # Build Inter-station Block Sections
        self._block_sections = []
        for i in range(len(self._stations) - 1):
            s_from = self._stations[i]
            s_to = self._stations[i+1]
            dist = round(s_to.chainage_km - s_from.chainage_km, 2)
            bs = BlockSection(
                section_id=f"{s_from.code}-{s_to.code}",
                from_station=s_from.code,
                to_station=s_to.code,
                length_km=dist,
                num_lines=2,
                up_max_speed_kmh=110,
                dn_max_speed_kmh=110,
                signalling_type="AUTOMATIC",
                is_blocked=False
            )
            self._block_sections.append(bs)

        # 3. Parse Passenger Schedules
        sched_path = SAMPLE_DATA_DIR / "KTV_PSA_Passenger_Schedule.xlsx"
        df_train_meta = pd.read_excel(sched_path, sheet_name="TRAIN-KTV-PSA")
        df_sched = pd.read_excel(sched_path, sheet_name="SCHEDULE-KTV-PSA")
        
        meta_dict = {}
        for _, r in df_train_meta.iterrows():
            t_num = str(r["TRAIN_NUMBER"]).strip()
            meta_dict[t_num] = {
                "name": str(r["TRAIN_NAME"]).strip(),
                "type": str(r["TRAIN_TYPE"]).strip().upper(),
                "color": str(r.get("FORECOLOR", "Blue")).strip()
            }

        # Group timetable rows by TRAIN_NO
        self._trains = []
        grouped = df_sched.groupby("TRAIN_NO")
        
        # Color mapping for authentic railway graphics
        color_map = {
            TrainPriority.P1_PREMIUM: "#f43f5e",     # Ruby/Crimson
            TrainPriority.P2_SUPERFAST: "#0ea5e9",   # Cyan/Sky
            TrainPriority.P3_EXPRESS: "#a855f7",     # Purple
            TrainPriority.P4_FREIGHT_LOADED: "#f59e0b", # Amber/Gold
            TrainPriority.P5_FREIGHT_EMPTY: "#64748b",  # Slate
            TrainPriority.P6_MAINTENANCE: "#10b981",    # Emerald
        }

        sttn_codes = [s.code for s in self._stations]
        sttn_idx_map = {code: i for i, code in enumerate(sttn_codes)}

        for train_no_val, group in grouped:
            train_no = str(train_no_val).strip()
            meta = meta_dict.get(train_no, {"name": f"TRAIN-{train_no}", "type": "MEX", "color": "Blue"})
            name = meta["name"]
            ttype = meta["type"]

            # Classify Priority
            upper_name = name.upper()
            if "VANDE" in upper_name or "RAJDHANI" in upper_name or "SHATABDI" in upper_name or ttype == "TEJ":
                prio = TrainPriority.P1_PREMIUM
                max_speed = 130
            elif ttype == "SUF" or "SF" in upper_name or "SUPERFAST" in upper_name:
                prio = TrainPriority.P2_SUPERFAST
                max_speed = 110
            else:
                prio = TrainPriority.P3_EXPRESS
                max_speed = 100

            # Deduplicate by station code and filter to corridor
            dedup_group = group.drop_duplicates(subset=["STTN_CODE"]).copy()
            corridor_rows = []
            for _, srow in dedup_group.iterrows():
                scode = str(srow["STTN_CODE"]).strip().upper()
                if scode in sttn_idx_map and pd.notna(srow["ARRIVAL"]):
                    corridor_rows.append(srow)

            if len(corridor_rows) < 2:
                continue

            # Determine true physical direction from start and end arrival times
            first_arr = int(corridor_rows[0]["ARRIVAL"])
            last_arr = int(corridor_rows[-1]["ARRIVAL"])
            is_dn = first_arr > last_arr

            # If DN (PSA -> KTV), the train visited PSA first and KTV last, so reverse rows
            if is_dn:
                corridor_rows = list(reversed(corridor_rows))

            direction = TrainDirection.DN if is_dn else TrainDirection.UP

            # Normalize times monotonically
            t_orig_start = int(corridor_rows[0]["ARRIVAL"])
            base_time_sec = t_orig_start % 86400

            stops: List[ScheduleStop] = []
            prev_dep = base_time_sec
            for srow in corridor_rows:
                scode = str(srow["STTN_CODE"]).strip().upper()
                raw_arr = int(srow["ARRIVAL"])
                raw_dep = int(srow["DEPARTURE"]) if pd.notna(srow["DEPARTURE"]) else raw_arr
                
                # Elapsed running seconds from entry
                elapsed_arr = raw_arr - t_orig_start
                elapsed_dep = raw_dep - t_orig_start

                arr_sec = base_time_sec + elapsed_arr
                dep_sec = base_time_sec + elapsed_dep
                
                # Ensure strictly non-decreasing progression
                if arr_sec < prev_dep:
                    arr_sec = prev_dep + 180
                if dep_sec < arr_sec:
                    dep_sec = arr_sec + 120
                prev_dep = dep_sec

                is_halt = str(srow.get("HALT_FLAG", "N")).strip().upper() == "Y"
                pf_raw = str(srow.get("PLATFORM", "")).strip() if pd.notna(srow.get("PLATFORM")) else ""
                pf = None
                if "PF-" in pf_raw:
                    parts = [p.strip() for p in pf_raw.split(",") if "PF-" in p]
                    if parts:
                        pf = parts[0]

                stops.append(ScheduleStop(
                    station_code=scode,
                    scheduled_arrival=arr_sec,
                    scheduled_departure=dep_sec,
                    actual_arrival=arr_sec,
                    actual_departure=dep_sec,
                    is_commercial_halt=is_halt,
                    platform=pf,
                    assigned_line="2" if prio in [TrainPriority.P1_PREMIUM, TrainPriority.P2_SUPERFAST] else "1",
                    delay_arrival_mins=0.0,
                    delay_departure_mins=0.0
                ))

            t_obj = Train(
                train_id=f"T-{train_no}",
                train_number=train_no,
                name=name,
                train_type=ttype,
                priority=prio,
                direction=direction,
                length_meters=600.0,
                max_speed_kmh=max_speed,
                color=color_map[prio],
                stops=stops
            )
            self._trains.append(t_obj)
            self._train_map[train_no] = t_obj

        # 4. Synthesize Freight Rakes from WAT_GOODS_TRAIN
        self._inject_goods_trains(color_map, sttn_idx_map)
        
        # Sort all trains chronologically by section entry time for authentic dispatching
        self._trains.sort(key=lambda t: t.stops[0].scheduled_arrival if t.stops else 0)
        logger.info(f"Initialized total {len(self._trains)} trains (Passenger + Goods) chronologically ordered.")

    def _inject_goods_trains(self, color_map, sttn_idx_map):
        """Inject representative heavy freight rakes running through KTV-PSA."""
        freight_templates = [
            {"num": "BOXN-7041", "name": "COAL-TALCHER-SPL", "type": "BOXN", "dir": TrainDirection.DN, "base_time": 18000, "speed": 60, "prio": TrainPriority.P4_FREIGHT_LOADED},
            {"num": "BCNA-2290", "name": "FOODGRAIN-FCI-UP", "type": "BCN", "dir": TrainDirection.UP, "base_time": 25200, "speed": 55, "prio": TrainPriority.P4_FREIGHT_LOADED},
            {"num": "BOXNHL-512", "name": "IRON-ORE-KK-LINE", "type": "BOXNHL", "dir": TrainDirection.DN, "base_time": 39600, "speed": 50, "prio": TrainPriority.P4_FREIGHT_LOADED},
            {"num": "BLCA-9011", "name": "CONTAINER-CONCOR-UP", "type": "BLCA", "dir": TrainDirection.UP, "base_time": 50400, "speed": 75, "prio": TrainPriority.P4_FREIGHT_LOADED},
            {"num": "EM-BCN-104", "name": "EMPTY-RAKE-PSA-WAT", "type": "BCN-E", "dir": TrainDirection.DN, "base_time": 61200, "speed": 65, "prio": TrainPriority.P5_FREIGHT_EMPTY},
            {"num": "TWR-801", "name": "OHE-INSPECTION-CAR", "type": "TWR", "dir": TrainDirection.UP, "base_time": 72000, "speed": 40, "prio": TrainPriority.P6_MAINTENANCE},
        ]

        sttn_order = self._stations if True else []
        for ft in freight_templates:
            direction = ft["dir"]
            ordered = list(self._stations) if direction == TrainDirection.UP else list(reversed(self._stations))
            cur_time = ft["base_time"]
            stops: List[ScheduleStop] = []

            for i, sttn in enumerate(ordered):
                if i > 0:
                    prev = ordered[i-1]
                    dist = abs(sttn.chainage_km - prev.chainage_km)
                    run_sec = int((dist / ft["speed"]) * 3600)
                    cur_time += run_sec
                
                # Goods trains generally run through without commercial halts, but can be looped
                arr = cur_time
                dep = cur_time
                stops.append(ScheduleStop(
                    station_code=sttn.code,
                    scheduled_arrival=arr,
                    scheduled_departure=dep,
                    actual_arrival=arr,
                    actual_departure=dep,
                    is_commercial_halt=False,
                    assigned_line="1" if direction == TrainDirection.UP else "4"
                ))

            t_obj = Train(
                train_id=f"G-{ft['num']}",
                train_number=ft["num"],
                name=ft["name"],
                train_type=ft["type"],
                priority=ft["prio"],
                direction=direction,
                length_meters=680.0,
                max_speed_kmh=ft["speed"],
                color=color_map[ft["prio"]],
                stops=stops
            )
            self._trains.append(t_obj)
            self._train_map[ft["num"]] = t_obj

    def _save_to_cache(self):
        try:
            data = {
                "stations": [s.model_dump() for s in self._stations],
                "blocks": [b.model_dump() for b in self._block_sections],
                "trains": [t.model_dump() for t in self._trains]
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            logger.info(f"Cached corridor dataset to {CACHE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _load_from_cache(self):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._stations = [Station(**s) for s in data["stations"]]
        self._station_map = {s.code: s for s in self._stations}
        self._block_sections = [BlockSection(**b) for b in data["blocks"]]
        self._trains = [Train(**t) for t in data["trains"]]
        self._train_map = {t.train_number: t for t in self._trains}

    # BaseDataSource Implementations
    def get_corridor_stations(self) -> List[Station]:
        return self._stations

    def get_block_sections(self) -> List[BlockSection]:
        return self._block_sections

    def get_active_trains(self, start_sec: int = 0, end_sec: int = 86400) -> List[Train]:
        """Filter trains that have at least one stop within the time window."""
        result = []
        for t in self._trains:
            if not t.stops:
                continue
            first_arr = t.stops[0].scheduled_arrival
            last_dep = t.stops[-1].scheduled_departure
            if (first_arr <= end_sec and last_dep >= start_sec):
                result.append(t)
        return result

    def update_train_positions(self, updates: List[Dict]) -> bool:
        for upd in updates:
            t_num = str(upd.get("train_number"))
            if t_num in self._train_map:
                train = self._train_map[t_num]
                sttn_code = upd.get("station_code")
                arr_delay = float(upd.get("delay_arrival_mins", 0.0))
                dep_delay = float(upd.get("delay_departure_mins", 0.0))
                for stop in train.stops:
                    if stop.station_code == sttn_code:
                        stop.delay_arrival_mins = arr_delay
                        stop.delay_departure_mins = dep_delay
                        stop.actual_arrival = stop.scheduled_arrival + int(arr_delay * 60)
                        stop.actual_departure = stop.scheduled_departure + int(dep_delay * 60)
        return True

    def submit_controller_decision(self, decision: ControllerDecision) -> bool:
        logger.info(f"Controller Decision Recorded: ID={decision.decision_id}, RecID={decision.recommendation_id}, Action={decision.action_taken}")
        return True

    def get_health_status(self) -> Dict[str, str]:
        return {
            "mode": "SAMPLE_DATA_OFFLINE_TWIN",
            "status": "HEALTHY",
            "corridor": f"{settings.SECTION_CODE} ({settings.SECTION_NAME})",
            "stations_loaded": str(len(self._stations)),
            "active_trains": str(len(self._trains)),
            "sync_latency_ms": "0.1"
        }
