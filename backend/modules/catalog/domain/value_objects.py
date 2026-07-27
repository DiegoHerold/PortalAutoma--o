from __future__ import annotations

import re
from dataclasses import dataclass


AUTOMATION_KEY_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


@dataclass(frozen=True)
class AutomationKey:
    value: str

    def __post_init__(self) -> None:
        if not AUTOMATION_KEY_RE.match(self.value):
            raise ValueError("Automation key must be lowercase and stable, e.g. dominio.importar_documentos.")


@dataclass(frozen=True)
class SemVer:
    value: str

    def __post_init__(self) -> None:
        if not SEMVER_RE.match(self.value):
            raise ValueError("Version must be SemVer, e.g. 1.2.0.")


@dataclass(frozen=True)
class ContentHash:
    algorithm: str
    value: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("Only sha256 hashes are supported.")
        if not re.fullmatch(r"[a-f0-9]{64}", self.value):
            raise ValueError("sha256 must be a 64-character lowercase hexadecimal value.")
