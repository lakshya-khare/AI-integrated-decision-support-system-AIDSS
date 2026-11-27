"""
Railway Network Topology & Conflict Detection Engine
Models track geometry, Clear Standing Room (CSR), inter-station headways, and bottleneck points.
"""

from typing import List, Dict, Tuple, Optional, Any
import math
from backend.domain.models import (
    Station, BlockSection, Train, ScheduleStop, Conflict, ConflictType, TrainPriority, TrainDirection
)
from backend.config import settings


class NetworkEngine:
    def __init__(self, stations: List[Station], block_sections: List[BlockSection]):
        self.stations = stations
        self.block_sections = block_sections
        self.station_map: Dict[str, Station] = {s.code: s for s in stations}
        self.block_map: Dict[str, BlockSection] = {b.section_id: b for b in block_sections}
        self.station_indices: Dict[str, int] = {s.code: i for i, s in enumerate(stations)}

    def get_distance_between(self, from_code: str, to_code: str) -> float:
        s1 = self.station_map.get(from_code)
        s2 = self.station_map.get(to_code)
        if not s1 or not s2:
            return 0.0
        return abs(s2.chainage_km - s1.chainage_km)

    def get_block_between(self, sttn_a: str, sttn_b: str) -> Optional[BlockSection]:
        key1 = f"{sttn_a}-{sttn_b}"
        key2 = f"{sttn_b}-{sttn_a}"
        return self.block_map.get(key1) or self.block_map.get(key2)

    def can_fit_in_loop(self, station_code: str, train_length_m: float) -> Tuple[bool, Optional[str]]:
        """Checks if station has an available loop line with CSR >= train length."""
        sttn = self.station_map.get(station_code)
        if not sttn:
            return False, None
        
        for line in sttn.lines:
            if line.line_type.value == "LOOP" and line.csr_length_m >= train_length_m:
                return True, line.line_number
        return False, None

    def detect_conflicts(self, trains: List[Train], headway_sec: int = settings.DEFAULT_HEADWAY_SECONDS) -> List[Conflict]:
        """
        Detects operational headway violations, station track clashes, and overtake bottlenecks.
        """
        conflicts: List[Conflict] = []
        c_count = 1

        # 1. Block Section Headway and Overtake Detection
        # Build station arrival timeline for each station
        sttn_arrivals: Dict[str, List[Tuple[int, int, Train, ScheduleStop]]] = {}
        for t in trains:
            for s in t.stops:
                arr = s.actual_arrival if s.actual_arrival is not None else s.scheduled_arrival
                dep = s.actual_departure if s.actual_departure is not None else s.scheduled_departure
                sttn_arrivals.setdefault(s.station_code, []).append((arr, dep, t, s))

        for sttn_code, arrivals in sttn_arrivals.items():
            arrivals.sort(key=lambda x: x[0])  # Sort by arrival time
            for i in range(len(arrivals) - 1):
                arr1, dep1, t1, s1 = arrivals[i]
                arr2, dep2, t2, s2 = arrivals[i+1]

                # Same direction check
                if t1.direction == t2.direction:
                    gap = arr2 - arr1
                    if 0 <= gap < headway_sec:
                        # Headway violation
                        conflicts.append(Conflict(
                            conflict_id=f"CONF-HW-{c_count:03d}",
                            conflict_type=ConflictType.HEADWAY_VIOLATION,
                            train_1=t1.train_number,
                            train_2=t2.train_number,
                            location=sttn_code,
                            time_window_start=arr1,
                            time_window_end=arr2,
                            severity="CRITICAL" if gap < 120 else "HIGH",
                            description=f"Dangerous headway gap ({gap}s < {headway_sec}s safe limit) between {t1.name} and {t2.name} at {sttn_code}"
                        ))
                        c_count += 1

                    # Check for Precedence / Slower Freight Blocking High-Priority Express
                    if t1.priority.weight < t2.priority.weight and gap < 900:  # Within 15 minutes
                        conflicts.append(Conflict(
                            conflict_id=f"CONF-PREC-{c_count:03d}",
                            conflict_type=ConflictType.PRECEDENCE_OVERTAKE,
                            train_1=t1.train_number,
                            train_2=t2.train_number,
                            location=sttn_code,
                            time_window_start=arr1,
                            time_window_end=arr2 + 600,
                            severity="HIGH",
                            description=f"Precedence bottleneck: Lower priority {t1.name} ({t1.priority.value}) preceding {t2.name} ({t2.priority.value}) approaching {sttn_code}"
                        ))
                        c_count += 1

                # Simultaneous Station Line Occupancy
                if s1.assigned_line and s2.assigned_line and s1.assigned_line == s2.assigned_line:
                    # Check temporal overlap
                    if max(arr1, arr2) < min(dep1, dep2):
                        conflicts.append(Conflict(
                            conflict_id=f"CONF-PF-{c_count:03d}",
                            conflict_type=ConflictType.PLATFORM_OVERLAP,
                            train_1=t1.train_number,
                            train_2=t2.train_number,
                            location=sttn_code,
                            time_window_start=max(arr1, arr2),
                            time_window_end=min(dep1, dep2),
                            severity="CRITICAL",
                            description=f"Track line {s1.assigned_line} overlap at {sttn_code} between {t1.train_number} and {t2.train_number}"
                        ))
                        c_count += 1

        return conflicts

    def get_realtime_positions(self, trains: List[Train], time_sec: int) -> List[Dict[str, Any]]:
        """
        Computes the exact physical position, speed, and track occupancy of every train
        at the specified operational timestamp.
        """
        positions = []
        for t in trains:
            if not t.stops or len(t.stops) < 2:
                continue

            t_start = t.stops[0].actual_departure if t.stops[0].actual_departure is not None else t.stops[0].scheduled_departure
            t_end = t.stops[-1].actual_arrival if t.stops[-1].actual_arrival is not None else t.stops[-1].scheduled_arrival

            if time_sec < t_start:
                positions.append({
                    "train_number": t.train_number,
                    "train_name": t.name,
                    "train_type": t.train_type,
                    "priority": t.priority.value,
                    "direction": t.direction.value,
                    "color": t.color,
                    "status": "UPCOMING",
                    "next_entry_station": t.stops[0].station_code,
                    "entry_time_sec": t_start
                })
                continue

            if time_sec > t_end:
                positions.append({
                    "train_number": t.train_number,
                    "train_name": t.name,
                    "train_type": t.train_type,
                    "priority": t.priority.value,
                    "direction": t.direction.value,
                    "color": t.color,
                    "status": "COMPLETED",
                    "cleared_corridor": True
                })
                continue

            # Train is currently on the section! Check if at a station or in a block section
            placed = False
            for i in range(len(t.stops)):
                stop = t.stops[i]
                arr = stop.actual_arrival if stop.actual_arrival is not None else stop.scheduled_arrival
                dep = stop.actual_departure if stop.actual_departure is not None else stop.scheduled_departure
                sttn_meta = self.station_map.get(stop.station_code)
                chainage = sttn_meta.chainage_km if sttn_meta else 0.0

                # Check if currently stopped/dwelling at this station
                if arr <= time_sec <= dep:
                    positions.append({
                        "train_number": t.train_number,
                        "train_name": t.name,
                        "train_type": t.train_type,
                        "priority": t.priority.value,
                        "direction": t.direction.value,
                        "color": t.color,
                        "status": "HALTED",
                        "location_type": "STATION",
                        "station_code": stop.station_code,
                        "station_name": sttn_meta.name if sttn_meta else stop.station_code,
                        "chainage_km": chainage,
                        "assigned_line": stop.assigned_line or ("2" if t.direction == TrainDirection.UP else "3"),
                        "platform": stop.platform or "PF-1",
                        "dwell_remaining_sec": max(0, dep - time_sec),
                        "speed_kmh": 0,
                        "is_loop": stop.assigned_line in ["1", "4"]
                    })
                    placed = True
                    break

                # Check if in transit between stop i and stop i+1
                if i < len(t.stops) - 1:
                    next_stop = t.stops[i+1]
                    next_arr = next_stop.actual_arrival if next_stop.actual_arrival is not None else next_stop.scheduled_arrival
                    next_sttn_meta = self.station_map.get(next_stop.station_code)
                    next_chainage = next_sttn_meta.chainage_km if next_sttn_meta else chainage

                    if dep < time_sec < next_arr:
                        run_duration = max(1, next_arr - dep)
                        elapsed = time_sec - dep
                        progress = min(1.0, max(0.0, elapsed / run_duration))
                        curr_km = round(chainage + progress * (next_chainage - chainage), 2)

                        positions.append({
                            "train_number": t.train_number,
                            "train_name": t.name,
                            "train_type": t.train_type,
                            "priority": t.priority.value,
                            "direction": t.direction.value,
                            "color": t.color,
                            "status": "RUNNING",
                            "location_type": "BLOCK_SECTION",
                            "from_station": stop.station_code,
                            "to_station": next_stop.station_code,
                            "block_id": f"{stop.station_code}-{next_stop.station_code}",
                            "chainage_km": curr_km,
                            "progress_percent": round(progress * 100, 1),
                            "speed_kmh": t.max_speed_kmh,
                            "eta_next_station_sec": max(0, next_arr - time_sec)
                        })
                        placed = True
                        break

        return positions
