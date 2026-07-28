from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CandidateScoringWeights:
    capacity: float = 30
    resource_headroom: float = 20
    package_affinity: float = 15
    runtime_affinity: float = 15
    stability: float = 10
    fairness: float = 10
    preferred_agent: float = 10

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "CandidateScoringWeights":
        if not isinstance(config, dict):
            return cls()
        values = {}
        for field_name in cls.__dataclass_fields__:
            value = config.get(field_name)
            if isinstance(value, (int, float)) and value >= 0:
                values[field_name] = float(value)
        return cls(**values)

    def to_payload(self) -> dict[str, float]:
        return {field_name: float(getattr(self, field_name)) for field_name in self.__dataclass_fields__}


@dataclass(frozen=True)
class CandidateScoreInput:
    available_pool_units: int
    required_pool_units: int
    cpu_usage_percentage: float | None
    memory_available_mb: int | None
    memory_required_mb: int
    package_cached: bool
    runtime_cached: bool
    preferred_agent: bool
    active_attempts: int = 0
    stability_factor: float = 1.0


def calculate_candidate_score(data: CandidateScoreInput, weights: CandidateScoringWeights) -> tuple[float, dict[str, float]]:
    capacity_ratio = 0.0
    if data.required_pool_units > 0:
        capacity_ratio = min(max(data.available_pool_units / data.required_pool_units, 0), 3) / 3
    cpu_headroom = 1.0 - min(max((data.cpu_usage_percentage or 0) / 100, 0), 1)
    memory_headroom = 0.0
    if data.memory_required_mb > 0 and data.memory_available_mb is not None:
        memory_headroom = min(max(data.memory_available_mb / data.memory_required_mb, 0), 3) / 3
    resource_headroom = (cpu_headroom + memory_headroom) / 2
    fairness = 1 / (1 + max(data.active_attempts, 0))

    components = {
        "capacity": round(weights.capacity * capacity_ratio, 4),
        "resource_headroom": round(weights.resource_headroom * resource_headroom, 4),
        "package_affinity": weights.package_affinity if data.package_cached else 0,
        "runtime_affinity": weights.runtime_affinity if data.runtime_cached else 0,
        "stability": round(weights.stability * max(min(data.stability_factor, 1), 0), 4),
        "fairness": round(weights.fairness * fairness, 4),
        "preferred_agent": weights.preferred_agent if data.preferred_agent else 0,
    }
    total = round(sum(components.values()), 4)
    return total, components
