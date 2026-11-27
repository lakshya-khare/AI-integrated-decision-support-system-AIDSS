"""
Data Source Interface Definition
Enables seamless switching between offline sample dataset and live TMS/COA feeds.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from backend.domain.models import Station, BlockSection, Train, DispatchRecommendation, ControllerDecision, SectionKPIs


class BaseDataSource(ABC):
    """
    Abstract interface for railway operational data.
    Decouples the optimization and decision logic from underlying storage/protocols.
    """

    @abstractmethod
    def get_corridor_stations(self) -> List[Station]:
        """Returns sequence of stations with chainage and line layouts."""
        pass

    @abstractmethod
    def get_block_sections(self) -> List[BlockSection]:
        """Returns all inter-station block sections."""
        pass

    @abstractmethod
    def get_active_trains(self, start_sec: int, end_sec: int) -> List[Train]:
        """Returns trains operating within the specified time window."""
        pass

    @abstractmethod
    def update_train_positions(self, updates: List[Dict]) -> bool:
        """Injects live position/delay telemetry."""
        pass

    @abstractmethod
    def submit_controller_decision(self, decision: ControllerDecision) -> bool:
        """Transmits approved/overridden dispatch command to field signalling/TMS."""
        pass

    @abstractmethod
    def get_health_status(self) -> Dict[str, str]:
        """Returns connectivity and sync health."""
        pass
