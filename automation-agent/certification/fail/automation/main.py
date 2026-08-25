"""
certification.fail

Deterministic, safe failure. Starts normally, emits a log line and a partial
progress marker, then raises a known, well-formed exception. The Python
process bootstrap (Agent.ExecutionHost/Launchers/RuntimeLauncher.cs ::
BuildPythonFunction) does not catch exceptions raised by the automation
function, so the interpreter exits with a non-zero code and the traceback
lands in stderr.log. ExecutionManager.ExecuteAsync then observes exitCode !=
0 and transitions the attempt to Failed, with
ExecutionResult.ErrorOutput populated from stderr (see
Agent.Application/Execution/ResultCollector.cs::ReadErrorAsync).

CERTIFICATION_FAILURE is a stable, greppable marker so the harness's
observation helper can assert on the *reason* for failure, not just on
"non-zero exit code".
"""

from __future__ import annotations


class CertificationFailure(RuntimeError):
    pass


def run(context: dict) -> dict:
    print("certification started")
    print("progress 50")
    print("raising deterministic failure: CERTIFICATION_FAILURE")
    raise CertificationFailure("CERTIFICATION_FAILURE: deterministic certification failure")
