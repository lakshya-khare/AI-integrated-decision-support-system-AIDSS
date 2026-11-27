"""
AIDSS System Configuration
East Coast Railway | Waltair Division | KTV-PSA Section
"""

import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DATA_DIR = BASE_DIR / "Sample Data"

class Settings(BaseModel):
    PROJECT_NAME: str = "AIDSS Rail Traffic Controller"
    VERSION: str = "2.4.0-PROD"
    ZONE: str = "ECoR"
    DIVISION: str = "WAT"
    SECTION_CODE: str = "KTV-PSA"
    SECTION_NAME: str = "Kottavalasa - Palasa Section"
    CORRIDOR_LENGTH_KM: float = 176.83
    TOTAL_STATIONS: int = 22
    
    # Operational Constants
    DEFAULT_HEADWAY_SECONDS: int = 300       # 5 minutes minimum separation between successive trains
    STATION_CLEARING_TIME_SECONDS: int = 180 # 3 minutes point operation & interlocking
    MIN_PASSENGER_HALT_SECONDS: int = 120    # 2 minutes minimum dwell for scheduled stops
    MAX_LOOP_OCCUPANCY_HOURS: float = 4.0    # Maximum permitted holding time on loop line
    
    # Solver Parameters
    SOLVER_TIMEOUT_SECONDS: int = 5          # Rapid re-optimization window for Section Controller
    ENABLE_HEURISTIC_FALLBACK: bool = True
    
    # Data Mode: "sample" or "live_tms"
    DATA_SOURCE_MODE: str = os.getenv("AIDSS_DATA_MODE", "sample")
    LIVE_TMS_ENDPOINT: str = os.getenv("TMS_API_URL", "https://tms.railnet.gov.in/api/v1/wat/ktv-psa")
    LIVE_TMS_API_KEY: str = os.getenv("TMS_API_KEY", "")
    
    # Storage
    AUDIT_LOG_FILE: Path = BASE_DIR / "audit_log.json"

settings = Settings()
