from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from modules.fleet.application.dto import AutomationWorkerPreferenceDTO


class AutomationWorkerPreferenceRepository(Protocol):
    def list_for_automation(self, automation_id: int) -> list[AutomationWorkerPreferenceDTO]:
        raise NotImplementedError

    def replace_for_automation(self, automation_id: int, preferences: list[dict]) -> list[AutomationWorkerPreferenceDTO]:
        raise NotImplementedError


@dataclass
class GetAutomationWorkerPreferences:
    preferences: AutomationWorkerPreferenceRepository

    def execute(self, automation_id: int) -> list[AutomationWorkerPreferenceDTO]:
        return self.preferences.list_for_automation(automation_id)


@dataclass
class ReplaceAutomationWorkerPreferences:
    preferences: AutomationWorkerPreferenceRepository

    def execute(self, automation_id: int, preferences: list[dict]) -> list[AutomationWorkerPreferenceDTO]:
        normalized = [
            {
                "worker_id": int(item["worker_id"]),
                "priority_order": int(item["priority_order"]),
            }
            for item in preferences
        ]
        return self.preferences.replace_for_automation(automation_id, normalized)
