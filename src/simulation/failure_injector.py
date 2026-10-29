"""Failure injection module for Scenario E: runtime failure injection driven by scenario config."""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from src.schemas.scenario import ScenarioConfig, FailureConfig

logger = logging.getLogger(__name__)


class FailureType:
    """Supported failure types matching scenario_e.yaml"""
    PV_INVERTER = "pv_inverter"
    BATTERY = "battery"
    EV_CHARGER = "ev_charger"
    SENSOR = "sensor"
    GRID_LIMIT = "grid_limit"


@dataclass
class ActiveFailure:
    """Represents a currently active failure."""
    failure_id: str
    asset_id: str
    failure_type: str
    severity: float
    start_timestep: int
    end_timestep: Optional[int]
    config: FailureConfig


class FailureInjector:
    """
    Injects failures declared in scenario config at scheduled timesteps during co-simulation.
    
    Reads FailureConfig objects from scenario_config.failures and applies them to the
    simulation state at the appropriate timesteps.
    """
    
    def __init__(self, scenario_config: ScenarioConfig):
        self.scenario_config = scenario_config
        self.failures = scenario_config.failures
        self.timestep_minutes = scenario_config.timestep_minutes
        self.simulation_start_datetime: Optional[datetime] = None
        
        # Parse start/end times to timesteps
        self.parsed_failures = self._parse_failure_times()
        
        # Active failures state
        self.active_failures: Dict[str, ActiveFailure] = {}
        self.failure_history: List[Dict[str, Any]] = []  # Log of all failure events
        
        # Current simulation state
        self.current_timestep = 0
    
    def _parse_failure_times(self) -> List[Dict[str, Any]]:
        """Parse failure start/end times to timestep indices."""
        parsed = []
        
        if self.simulation_start_datetime is None:
            # Parse from first building's simulation_start
            for building in self.scenario_config.buildings:
                if building.simulation_start:
                    try:
                        self.simulation_start_datetime = datetime.fromisoformat(building.simulation_start)
                        break
                    except ValueError:
                        continue
        
        for failure in self.failures:
            start_timestep = self._time_to_timestep(failure.start_time)
            end_timestep = None
            if failure.end_time:
                end_timestep = self._time_to_timestep(failure.end_time)
            
            parsed.append({
                'config': failure,
                'start_timestep': start_timestep,
                'end_timestep': end_timestep,
            })
        
        return parsed
    
    def _time_to_timestep(self, time_str: str) -> int:
        """Convert time string (HH:MM or ISO datetime) to timestep index."""
        try:
            # Try parsing as full ISO datetime
            dt = datetime.fromisoformat(time_str)
            if self.simulation_start_datetime:
                delta = dt - self.simulation_start_datetime
                total_minutes = delta.total_seconds() / 60
                return int(total_minutes / self.timestep_minutes)
        except ValueError:
            pass
        
        # Try parsing as HH:MM (time of day) - assume day 0
        try:
            hour, minute = map(int, time_str.split(':'))
            total_minutes = hour * 60 + minute
            return int(total_minutes / self.timestep_minutes)
        except ValueError:
            logger.warning(f"Could not parse time: {time_str}, defaulting to timestep 0")
            return 0
    
    def set_simulation_start(self, start_datetime: datetime):
        """Set simulation start datetime for time parsing."""
        self.simulation_start_datetime = start_datetime
        self.parsed_failures = self._parse_failure_times()
    
    def reset(self):
        """Reset failure injector state."""
        self.active_failures = {}
        self.failure_history = []
        self.current_timestep = 0
    
    def step(self, timestep: int) -> Dict[str, List[ActiveFailure]]:
        """
        Advance to next timestep, activate/deactivate failures as scheduled.
        
        Returns dict with newly activated and newly deactivated failures at this timestep.
        """
        self.current_timestep = timestep
        newly_activated = []
        newly_deactivated = []
        
        # Check for new failures starting at this timestep
        for parsed in self.parsed_failures:
            config = parsed['config']
            start_ts = parsed['start_timestep']
            end_ts = parsed['end_timestep']
            
            # Activate failure
            if start_ts == timestep and config.failure_id not in self.active_failures:
                active = ActiveFailure(
                    failure_id=config.failure_id,
                    asset_id=config.asset_id,
                    failure_type=config.failure_type,
                    severity=config.severity,
                    start_timestep=start_ts,
                    end_timestep=end_ts,
                    config=config
                )
                self.active_failures[config.failure_id] = active
                newly_activated.append(active)
                
                self.failure_history.append({
                    'event': 'activated',
                    'timestep': timestep,
                    'failure_id': config.failure_id,
                    'asset_id': config.asset_id,
                    'failure_type': config.failure_type,
                    'severity': config.severity,
                })
                logger.info(f"Failure ACTIVATED at timestep {timestep}: {config.failure_id} ({config.failure_type}) on {config.asset_id}")
            
            # Deactivate failure
            if end_ts is not None and end_ts == timestep and config.failure_id in self.active_failures:
                active = self.active_failures.pop(config.failure_id)
                newly_deactivated.append(active)
                
                self.failure_history.append({
                    'event': 'deactivated',
                    'timestep': timestep,
                    'failure_id': config.failure_id,
                    'asset_id': config.asset_id,
                    'failure_type': config.failure_type,
                    'duration_timesteps': timestep - active.start_timestep,
                })
                logger.info(f"Failure DEACTIVATED at timestep {timestep}: {config.failure_id}")
        
        return {'activated': newly_activated, 'deactivated': newly_deactivated}
    
    def get_active_failures(self) -> List[ActiveFailure]:
        """Get list of currently active failures."""
        return list(self.active_failures.values())
    
    def is_asset_failed(self, asset_id: str) -> Optional[ActiveFailure]:
        """Check if a specific asset has an active failure."""
        for failure in self.active_failures.values():
            if failure.asset_id == asset_id:
                return failure
        return None
    
    def apply_pv_failure(self, building_pvs: Dict[str, float], building_id: str) -> float:
        """
        Apply PV inverter failure to building PV generation.
        
        Returns modified PV generation (0 or reduced by severity).
        """
        failure = self.is_asset_failed(f"{building_id}_pv")
        if failure and failure.failure_type == FailureType.PV_INVERTER:
            original = building_pvs.get(building_id, 0.0)
            return original * (1.0 - failure.severity)
        return building_pvs.get(building_id, 0.0)
    
    def apply_battery_failure(self, building_battery_powers: Dict[str, float], building_id: str) -> float:
        """
        Apply battery failure - set battery power to 0 (unavailable).
        
        Returns modified battery power.
        """
        failure = self.is_asset_failed(f"{building_id}_battery")
        if failure and failure.failure_type == FailureType.BATTERY:
            return 0.0  # Battery completely unavailable
        return building_battery_powers.get(building_id, 0.0)
    
    def apply_ev_charger_failure(self, building_ev_powers: Dict[str, float], asset_id: str) -> float:
        """
        Apply EV charger failure - reduce charging power by severity.
        
        Returns modified EV charging power.
        """
        failure = self.is_asset_failed(asset_id)
        if failure and failure.failure_type == FailureType.EV_CHARGER:
            original = building_ev_powers.get(asset_id, 0.0)
            # For charging (positive power), reduce by severity
            if original > 0:
                return original * (1.0 - failure.severity)
        return building_ev_powers.get(asset_id, 0.0)
    
    def apply_sensor_failure(self, observations: Dict[str, float], sensor_asset_id: str) -> Dict[str, float]:
        """
        Apply sensor failure - return NaN or zero for the failed sensor.
        
        Returns modified observations dict.
        """
        failure = self.is_asset_failed(sensor_asset_id)
        if failure and failure.failure_type == FailureType.SENSOR:
            # Return NaN to indicate failed sensor reading
            modified = observations.copy()
            modified[sensor_asset_id] = float('nan')
            return modified
        return observations
    
    def apply_grid_limit_failure(self, import_limit: float, export_limit: float) -> tuple:
        """
        Apply grid limit reduction failure.
        
        Returns modified (import_limit, export_limit).
        """
        failure = self.is_asset_failed("community_grid")
        if failure and failure.failure_type == FailureType.GRID_LIMIT:
            # Reduce import limit by severity
            modified_import = import_limit * (1.0 - failure.severity)
            modified_export = export_limit * (1.0 - failure.severity)
            return modified_import, modified_export
        return import_limit, export_limit
    
    def get_failure_summary(self) -> Dict[str, Any]:
        """Get summary of all failure events for reporting."""
        return {
            'total_failures_configured': len(self.parsed_failures),
            'failures_activated': len([e for e in self.failure_history if e['event'] == 'activated']),
            'failures_deactivated': len([e for e in self.failure_history if e['event'] == 'deactivated']),
            'currently_active': len(self.active_failures),
            'history': self.failure_history,
        }


def create_failure_injector(scenario_config: ScenarioConfig) -> FailureInjector:
    """Factory function to create FailureInjector from scenario config."""
    return FailureInjector(scenario_config)