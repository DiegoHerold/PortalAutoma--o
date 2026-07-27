from __future__ import annotations


def required_pool_for_execution_mode(mode: str) -> str:
    if mode == "interactive":
        return "interactive"
    if mode == "browser":
        return "browser"
    return "background"
