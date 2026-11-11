"""Portal-side helpers for the Portal-Agent certification harness.

See docs/certification-harness.md for the full design. Everything in this
package talks to the real Portal HTTP API (the same endpoints the frontend
and `.venv/Scripts/python gateway/agent_gateway/tests/smoke_*.py`
scripts use) — it does not write to the database directly and it does not
special-case "certification" anywhere in the Portal's own request handling.
"""
