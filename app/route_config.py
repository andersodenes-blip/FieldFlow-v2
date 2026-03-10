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
    travel_speed_kmh: float = 30.0
    parking_minutes: float = 10.0
    haversine_correction_factor: float = 1.2
    max_capacity_share: float = 0.65
    reassign_weights: ReassignWeights = field(default_factory=ReassignWeights)
    default_work_hours: float = 1.0
    max_capacity_fix_iterations: int = 100


# Per-region overrides (v1 parity)
# travel_speed_kmh=30, parking_minutes=10 for all regions
REGION_CONFIGS: dict[str, RegionRouteConfig] = {
    "Oslo": RegionRouteConfig(
        haversine_correction_factor=1.3,
    ),
    "Bergen": RegionRouteConfig(
        haversine_correction_factor=1.4,
    ),
    "Stavanger": RegionRouteConfig(
        haversine_correction_factor=1.49,
    ),
    "Drammen": RegionRouteConfig(
        haversine_correction_factor=1.2,
    ),
    "Innlandet": RegionRouteConfig(
        haversine_correction_factor=1.2,
    ),
    "Østfold": RegionRouteConfig(
        haversine_correction_factor=1.2,
    ),
}

# Default config for regions not listed above
DEFAULT_CONFIG = RegionRouteConfig()


def get_region_config(region_name: str) -> RegionRouteConfig:
    """Get route planning config for a region by name."""
    return REGION_CONFIGS.get(region_name, DEFAULT_CONFIG)
