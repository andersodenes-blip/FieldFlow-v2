# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Per-region route planning configuration.

Mirrors v1 config/*.json but hardcoded for simplicity.
Can be moved to database later.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReassignWeights:
    geo: float = 0.4
    month: float = 0.4
    capacity: float = 0.2


@dataclass(frozen=True)
class RegionRouteConfig:
    max_hours_per_day: float = 7.5
    travel_speed_kmh: float = 25.0
    parking_minutes: float = 15.0
    haversine_correction_factor: float = 1.0
    max_capacity_share: float = 0.65
    reassign_weights: ReassignWeights = field(default_factory=ReassignWeights)
    default_work_hours: float = 4.0
    max_capacity_fix_iterations: int = 100


# Per-region overrides
REGION_CONFIGS: dict[str, RegionRouteConfig] = {
    "Oslo": RegionRouteConfig(
        travel_speed_kmh=25.0,
        parking_minutes=15.0,
    ),
    "Bergen": RegionRouteConfig(
        travel_speed_kmh=30.0,
        parking_minutes=10.0,
    ),
    "Stavanger": RegionRouteConfig(
        travel_speed_kmh=30.0,
        parking_minutes=10.0,
        haversine_correction_factor=1.49,
    ),
    "Drammen": RegionRouteConfig(
        travel_speed_kmh=25.0,
        parking_minutes=15.0,
    ),
}

# Default config for regions not listed above
DEFAULT_CONFIG = RegionRouteConfig()


def get_region_config(region_name: str) -> RegionRouteConfig:
    """Get route planning config for a region by name."""
    return REGION_CONFIGS.get(region_name, DEFAULT_CONFIG)
