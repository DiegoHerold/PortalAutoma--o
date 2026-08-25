from __future__ import annotations

from tools.certification.execution import _extract_error_output


def test_extract_error_output_uses_attempt_error_message() -> None:
    text = "CERTIFICATION_FAILURE: deterministic certification failure"

    assert _extract_error_output({}, {"error_message": text}) == text


def test_extract_error_output_falls_back_to_result_error_message() -> None:
    text = "CERTIFICATION_FAILURE: deterministic certification failure"

    assert _extract_error_output(
        {"result": {"error": {"message": text}}},
        {},
    ) == text
