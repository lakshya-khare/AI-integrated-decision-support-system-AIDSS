"""
Domain Entities and Data Contracts
Authentic Indian Railways Operational Modeling (WAT Division / ECoR)
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TrainPriority(str, Enum):
    P1_PREMIUM = "P1_PREMIUM"          # Vande Bharat, Rajdhani, Tejas (Highest Precedence)
    P2_SUPERFAST = "P2_SUPERFAST"      # Superfast Express, Mail
    P3_EXPRESS = "P3_EXPRESS"          # Mail/Express, Passenger, MEMU
    P4_FREIGHT_LOADED = "P4_FREIGHT"   # BCN/BOXN Loaded rake (Coal, Iron Ore, Grain)
    P5_FREIGHT_EMPTY = "P5_EMPTY"      # Empty freight rakes / Light Engine
    P6_MAINTENANCE = "P6_MAINT"        # OHE Tower Wagon, Track Machine

    @property
    def weight(self) -> int:
        weights = {
            TrainPriority.P1_PREMIUM: 100,
            TrainPriority.P2_SUPERFAST: 60,
            TrainPriority.P3_EXPRESS: 35,
            TrainPriority.P4_FREIGHT_LOADED: 20,
            TrainPriority.P5_FREIGHT_EMPTY: 10,
            TrainPriority.P6_MAINTENANCE: 5,
        }
        return weights[self]


class TrainDirection(str, Enum):
    UP = "UP"  # Towards PSA (Northbound)
    DN = "DN"  # Towards KTV/VSKP (Southbound)


class LineType(str, Enum):
    MAIN = "MAIN"
    LOOP = "LOOP"
    SIDING = "SIDING"


class StationLine(BaseModel):
    station_code: str
    line_number: str = "1"
    line_type: LineType = LineType.LOOP
    csr_length_m: float = 720.0       # Clear Standing Room in meters
    speed_limit_kmh: int = 15          # 15 km/h for turnout/loop, 100-110 km/h for main
    has_platform: bool = False
    is_electrified: bool = True


class Station(BaseModel):
    sequence: int
    code: str
    name: str
    chainage_km: float                # Distance from KTV (0.00 km)
    inter_distance_km: float          # Distance to previous station
    is_junction: bool = False
    is_cabin: bool = False
    total_lines: int = 4
    lines: List[StationLine] = Field(default_factory=list)


class BlockSection(BaseModel):
    section_id: str                   # e.g., "KTV-KPL"
    from_station: str
    to_station: str
    length_km: float
    num_lines: int = 2                # Double line section
    up_max_speed_kmh: int = 110
    dn_max_speed_kmh: int = 110
    signalling_type: str = "AUTOMATIC" # Automatic Block Signalling
    is_blocked: bool = False          # Track maintenance or outage


class ScheduleStop(BaseModel):
    station_code: str
    scheduled_arrival: int            # Seconds from reference midnight
    scheduled_departure: int
    actual_arrival: Optional[int] = None
    actual_departure: Optional[int] = None
    is_commercial_halt: bool = False
    platform: Optional[str] = None
    assigned_line: Optional[str] = None
    delay_arrival_mins: float = 0.0
    delay_departure_mins: float = 0.0


class Train(BaseModel):
    train_id: str
    train_number: str
    name: str
    train_type: str                   # SUF, MEX, PASS, BCN, BOXN
    priority: TrainPriority
    direction: TrainDirection
    length_meters: float = 650.0      # Typical 24-coach passenger ~600m, goods rake ~650m
    max_speed_kmh: int = 100
    color: str = "#3b82f6"
    stops: List[ScheduleStop] = Field(default_factory=list)


class ConflictType(str, Enum):
    HEADWAY_VIOLATION = "HEADWAY_VIOLATION"      # Trains too close on block section
    OPPOSING_OCCUPANCY = "OPPOSING_OCCUPANCY"    # Bidirectional line conflict
    PLATFORM_OVERLAP = "PLATFORM_OVERLAP"        # Platform occupied by earlier train
    PRECEDENCE_OVERTAKE = "PRECEDENCE_OVERTAKE"  # Slower freight ahead of high-priority express
    CSR_LENGTH_EXCEEDED = "CSR_LENGTH_EXCEEDED"  # Train exceeds loop clear standing room


class Conflict(BaseModel):
    conflict_id: str
    conflict_type: ConflictType
    train_1: str                      # Train Number
    train_2: Optional[str] = None
    location: str                     # Station code or Block section ID
    time_window_start: int            # Seconds
    time_window_end: int
    severity: str = "HIGH"            # CRITICAL, HIGH, MEDIUM
    description: str


class ActionType(str, Enum):
    PROCEED_MAIN = "PROCEED_MAIN"
    LOOP_HOLD = "LOOP_HOLD"                     # Divert to loop and hold for overtake
    SPEED_REGULATION = "SPEED_REGULATION"       # Regulate section run time
    PLATFORM_DIVERSION = "PLATFORM_DIVERSION"   # Reallocate to alternate platform
    SINGLE_LINE_DISPATCH = "SINGLE_LINE_DISPATCH" # Pilot on wrong line during block


class DispatchRecommendation(BaseModel):
    recommendation_id: str
    train_number: str
    train_name: str
    station_code: str
    action: ActionType
    target_line: str = "1"
    hold_duration_sec: int
    rationale: str
    projected_delay_savings_mins: float
    status: str = "PENDING"           # PENDING, APPROVED, REJECTED, OVERRIDDEN, EXPIRED
    created_at: str
    target_time_sec: Optional[int] = None
    overtaking_train: Optional[str] = None
    is_approaching: Optional[bool] = None


class ControllerDecision(BaseModel):
    decision_id: str
    recommendation_id: str
    controller_id: str = "WAT-SCOR-01"
    action_taken: str                 # APPROVED, OVERRIDDEN, REJECTED
    override_reason: Optional[str] = None
    timestamp: str


class SectionKPIs(BaseModel):
    throughput_trains_24h: int
    active_trains_on_section: int
    average_delay_minutes: float
    punctuality_rate_percent: float
    track_utilization_percent: float
    conflicts_resolved_count: int
