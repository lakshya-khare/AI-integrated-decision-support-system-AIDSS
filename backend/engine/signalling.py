"""
Signalling, Interlocking Telemetry & Line Capacity Engine (Scott's Formula)
Authentic Indian Railways 4-Aspect Automatic Block Signalling & Corridor Throughput Optimization.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from backend.domain.models import Station, BlockSection, Train, TrainDirection, TrainPriority


class SignalAspect(BaseModel):
    signal_id: str
    station_code: str
    signal_name: str                  # e.g., "UP HOME", "UP STARTER", "DN ADV STARTER"
    aspect: str                       # "GREEN", "DOUBLE_YELLOW", "YELLOW", "RED"
    direction: str                    # "UP" or "DN"
    interlocking_locked: bool
    controlled_by_train: Optional[str] = None


class SectionThroughputMetrics(BaseModel):
    corridor_length_km: float = 176.83
    critical_block_section: str = "VZM-CPP"
    critical_block_running_time_mins: float = 12.5
    block_clearing_operation_time_mins: float = 5.0
    efficiency_factor: float = 0.80   # Indian Railways Standard E = 0.8
    theoretical_capacity_trains_24h: int
    chartered_trains_count: int
    saturation_index_percent: float
    available_freight_white_spaces: int
    bottleneck_station: str = "VIZIANAGARAM JN. (VZM)"


class SignallingTelemetryEngine:
    """
    Simulates real-time 4-Aspect Colour Light Automatic Signalling (MACLS)
    and computes Indian Railways Line Capacity utilizing Scott's Formula.
    """

    def __init__(self, stations: List[Station], block_sections: List[BlockSection]):
        self.stations = stations
        self.block_sections = block_sections

    def compute_scotts_capacity(self, active_trains_count: int) -> SectionThroughputMetrics:
        """
        Scott's Line Capacity Formula:
        C = (1440 / (T + t)) * E
        where:
          T = Running time over critical block section (mins)
          t = Block operation and clearing time (mins)
          E = Efficiency allowance (typically 0.70 to 0.80)
        """
        T = 12.5  # VZM-CPP critical section run time
        t = 5.0   # Block operation, point setting and sighting distance clearing
        E = 0.80

        # Capacity per track in 24 hours
        cap_per_track = (1440.0 / (T + t)) * E
        # Total double-line capacity (UP + DN)
        total_theoretical = int(cap_per_track * 2)

        chartered = active_trains_count
        saturation = round((chartered / max(total_theoretical, 1)) * 100, 1)
        white_spaces = max(0, total_theoretical - chartered)

        return SectionThroughputMetrics(
            corridor_length_km=176.83,
            critical_block_section="VZM-CPP (11.7 km)",
            critical_block_running_time_mins=T,
            block_clearing_operation_time_mins=t,
            efficiency_factor=E,
            theoretical_capacity_trains_24h=total_theoretical,
            chartered_trains_count=chartered,
            saturation_index_percent=saturation,
            available_freight_white_spaces=white_spaces,
            bottleneck_station="VIZIANAGARAM JN. (VZM)"
        )

    def get_live_signals(self, trains: List[Train], current_time_sec: int = 56700) -> List[SignalAspect]:
        """
        Computes 4-aspect automatic signal status for all 22 stations based on active train locations.
        Aspect Hierarchy:
        - RED: Train currently occupying the block section.
        - YELLOW: 1 block ahead clear, following block at RED.
        - DOUBLE_YELLOW: 2 blocks ahead clear, 3rd block at RED.
        - GREEN: 3 or more blocks completely clear.
        """
        # Determine train positions
        occupied_blocks_up = set()
        occupied_blocks_dn = set()

        for t in trains:
            if not t.stops:
                continue
            for i in range(len(t.stops) - 1):
                s1, s2 = t.stops[i], t.stops[i+1]
                t_dep = s1.actual_departure or s1.scheduled_departure
                t_arr = s2.actual_arrival or s2.scheduled_arrival

                if t_dep <= current_time_sec <= t_arr:
                    b_id = f"{s1.station_code}-{s2.station_code}"
                    if t.direction == TrainDirection.UP:
                        occupied_blocks_up.add(s1.station_code)
                    else:
                        occupied_blocks_dn.add(s1.station_code)

        signals: List[SignalAspect] = []
        for i, sttn in enumerate(self.stations):
            # UP Signalling
            if sttn.code in occupied_blocks_up:
                up_aspect = "RED"
                up_locked = True
            elif i < len(self.stations) - 1 and self.stations[i+1].code in occupied_blocks_up:
                up_aspect = "YELLOW"
                up_locked = False
            elif i < len(self.stations) - 2 and self.stations[i+2].code in occupied_blocks_up:
                up_aspect = "DOUBLE_YELLOW"
                up_locked = False
            else:
                up_aspect = "GREEN"
                up_locked = False

            signals.append(SignalAspect(
                signal_id=f"SIG-UP-{sttn.code}",
                station_code=sttn.code,
                signal_name=f"{sttn.code} UP STARTER",
                aspect=up_aspect,
                direction="UP",
                interlocking_locked=up_locked
            ))

            # DN Signalling
            if sttn.code in occupied_blocks_dn:
                dn_aspect = "RED"
                dn_locked = True
            elif i > 0 and self.stations[i-1].code in occupied_blocks_dn:
                dn_aspect = "YELLOW"
                dn_locked = False
            elif i > 1 and self.stations[i-2].code in occupied_blocks_dn:
                dn_aspect = "DOUBLE_YELLOW"
                dn_locked = False
            else:
                dn_aspect = "GREEN"
                dn_locked = False

            signals.append(SignalAspect(
                signal_id=f"SIG-DN-{sttn.code}",
                station_code=sttn.code,
                signal_name=f"{sttn.code} DN STARTER",
                aspect=dn_aspect,
                direction="DN",
                interlocking_locked=dn_locked
            ))

        return signals
