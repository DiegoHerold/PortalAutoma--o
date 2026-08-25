"""Thin real HTTP client for the Portal API, scoped to what the
certification harness needs: auth, categories, automations/versions,
package uploads, runtimes, agent registration, and executions.

Every method maps 1:1 to a route in `backend/modules/*/api/routes.py`. No
endpoint here is certification-specific — this is the same public API a
human operator or the frontend would call.

Deliberately dependency-light (httpx only) so it can run either inside the
backend container (`docker compose exec backend python -m
tools.certification.cli ...`) or from the harness's own environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


class PortalApiError(RuntimeError):
    """Raised when the Portal API returns an error response."""

    def __init__(self, method: str, url: str, response: httpx.Response) -> None:
        self.method = method
        self.url = url
        self.status_code = response.status_code
        try:
            self.detail: Any = response.json()
        except ValueError:
            self.detail = response.text
        super().__init__(f"{method} {url} -> {response.status_code}: {self.detail!r}")


@dataclass
class PortalApiClient:
    """Synchronous Portal API client.

    `base_url` should point at the `/api/v1` prefix, e.g.
    ``http://localhost:8000/api/v1`` from the host or
    ``http://backend:8000/api/v1`` from inside the compose network.
    """

    base_url: str
    timeout_seconds: float = 20.0
    _client: httpx.Client = field(init=False, repr=False)
    _bearer: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PortalApiClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- low-level -----------------------------------------------------

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {}
        if self._bearer:
            headers["Authorization"] = f"Bearer {self._bearer}"
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", {}) or {}
        response = self._client.request(method, path, headers=self._headers(headers), **kwargs)
        if response.status_code >= 400:
            raise PortalApiError(method, path, response)
        return response

    # -- health ----------------------------------------------------------

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health").json()

    def gateway_health(self) -> dict[str, Any]:
        return self._request("GET", "/agent-gateway/health").json()

    def gateway_readiness(self) -> dict[str, Any]:
        return self._request("GET", "/agent-gateway/readiness").json()

    # -- auth --------------------------------------------------------------

    def login(self, email: str, password: str) -> str:
        response = self._request("POST", "/auth/login", json={"email": email, "password": password})
        token = response.json()["access_token"]
        self._bearer = token
        return token

    # -- categories ----------------------------------------------------

    def list_categories(self) -> list[dict[str, Any]]:
        return self._request("GET", "/categories").json()

    def create_category(self, name: str, slug: str, description: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/categories",
            json={"name": name, "slug": slug, "description": description, "is_active": True},
        ).json()

    def get_or_create_category(self, name: str, slug: str, description: str | None = None) -> dict[str, Any]:
        for category in self.list_categories():
            if category.get("slug") == slug:
                return category
        return self.create_category(name, slug, description)

    # -- automations -----------------------------------------------------

    def list_automations(self) -> list[dict[str, Any]]:
        return self._request("GET", "/automations").json()

    def create_automation(
        self,
        *,
        key: str,
        name: str,
        slug: str,
        category_id: int,
        executor_type: str = "python_script",
        description: str | None = None,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/automations",
            json={
                "key": key,
                "name": name,
                "slug": slug,
                "description": description,
                "category_id": category_id,
                "executor_type": executor_type,
                "timeout_seconds": timeout_seconds,
                "is_active": True,
            },
        ).json()

    def get_or_create_automation(
        self,
        *,
        key: str,
        name: str,
        slug: str,
        category_id: int,
        description: str | None = None,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        for automation in self.list_automations():
            if automation.get("key") == key:
                return automation
        return self.create_automation(
            key=key,
            name=name,
            slug=slug,
            category_id=category_id,
            description=description,
            timeout_seconds=timeout_seconds,
        )

    def list_automation_versions(self, automation_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/automations/{automation_id}/versions").json()

    def create_automation_version(
        self,
        automation_id: int,
        raw_manifest: str,
        *,
        idempotency_key: str | None = None,
        release_notes: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._request(
            "POST",
            f"/automations/{automation_id}/versions",
            json={"raw_manifest": raw_manifest, "release_notes": release_notes},
            headers=headers,
        ).json()

    def get_or_create_automation_version(
        self, automation_id: int, version: str, raw_manifest: str
    ) -> dict[str, Any]:
        for existing in self.list_automation_versions(automation_id):
            if existing.get("version") == version:
                return existing
        return self.create_automation_version(
            automation_id, raw_manifest, idempotency_key=f"certification-version-{automation_id}-{version}"
        )

    def publish_automation_version(self, version_id: int) -> dict[str, Any]:
        return self._request("POST", f"/automation-versions/{version_id}/publish").json()

    # -- packages ----------------------------------------------------------

    def initiate_package_upload(
        self, version_id: int, file_name: str, expected_size_bytes: int, expected_sha256: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/automation-versions/{version_id}/package-uploads",
            json={
                "file_name": file_name,
                "expected_size_bytes": expected_size_bytes,
                "expected_sha256": expected_sha256,
            },
        ).json()

    def upload_package_bytes(self, upload_session_id: str, file_path: str, file_name: str) -> None:
        with open(file_path, "rb") as handle:
            self._request(
                "PUT",
                f"/package-uploads/{upload_session_id}/bytes",
                files={"file": (file_name, handle, "application/zip")},
            )

    def complete_package_upload(self, upload_session_id: str) -> dict[str, Any]:
        return self._request("POST", f"/package-uploads/{upload_session_id}/complete").json()

    # -- runtimes ------------------------------------------------------

    def list_runtimes(self) -> list[dict[str, Any]]:
        return self._request("GET", "/runtimes").json()

    def create_runtime(self, key: str, name: str, description: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST", "/runtimes", json={"key": key, "name": name, "description": description}
        ).json()

    def get_or_create_runtime(self, key: str, name: str) -> dict[str, Any]:
        for runtime in self.list_runtimes():
            if runtime.get("key") == key:
                return runtime
        return self.create_runtime(key, name)

    def create_runtime_version(
        self,
        runtime_id: str,
        version: str,
        *,
        operating_system: str = "windows",
        architecture: str = "x64",
        supported_entrypoints: list[str] | None = None,
        supported_execution_modes: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/runtimes/{runtime_id}/versions",
            json={
                "version": version,
                "operating_system": operating_system,
                "architecture": architecture,
                "supported_entrypoints": supported_entrypoints or ["python-function"],
                "supported_execution_modes": supported_execution_modes or ["background", "interactive"],
            },
        ).json()

    def get_or_create_runtime_version(self, runtime_id: str, version: str) -> dict[str, Any]:
        for existing in self._request("GET", f"/runtimes/{runtime_id}").json().get("versions", []):
            if existing.get("version") == version:
                return existing
        return self.create_runtime_version(runtime_id, version)

    def publish_runtime_version(self, runtime_version_id: str) -> dict[str, Any]:
        return self._request("POST", f"/runtime-versions/{runtime_version_id}/publish").json()

    def deprecate_runtime_version(self, runtime_version_id: str) -> dict[str, Any]:
        # Regressao/limitacao real do Portal: nao existe DELETE /runtimes nem
        # DELETE /runtime-versions - so publish/deprecate/block (routes.py).
        # "Apagar" um runtime do catalogo, na pratica hoje, significa
        # depreca-lo: ele sai do que a Portal oferece como runtime ativo
        # pra publicar automacoes novas, mas o registro/historico continua
        # existindo (auditoria). Usado por curate_runtime_catalog.py.
        return self._request("POST", f"/runtime-versions/{runtime_version_id}/deprecate").json()

    def get_runtime(self, runtime_id: str) -> dict[str, Any]:
        return self._request("GET", f"/runtimes/{runtime_id}").json()

    # -- dispatch diagnostics ---------------------------------------------

    def cancel_execution(self, execution_id: str, reason: str | None = None) -> dict[str, Any]:
        return self._request("POST", f"/executions/{execution_id}/cancel", json={"reason": reason}).json()

    def get_execution_dispatch(self, execution_id: str) -> dict[str, Any]:
        # Devolve o historico de "dispatch decisions" pra essa execucao -
        # cada rodada do agendador (ScheduleTaskExecution, modules/dispatch/
        # application/use_cases/scheduler.py) grava um snapshot dos agentes
        # candidatos avaliados e o motivo exato de cada um ter sido
        # rejeitado (reject_reason/reject_details). Usado por
        # diagnose_pending.py pra descobrir POR QUE uma execucao fica presa
        # em "pending" pra sempre, em vez de adivinhar.
        return self._request("GET", f"/executions/{execution_id}/dispatch").json()

    # -- agents (Fleet) --------------------------------------------------

    def create_registration_token(self, expires_in_seconds: int = 600) -> str:
        response = self._request(
            "POST", "/agents/registration-tokens", json={"expires_in_seconds": expires_in_seconds}
        )
        return response.json()["registration_token"]

    def register_agent(
        self,
        *,
        registration_token: str,
        local_identity: str,
        hostname: str,
        name: str,
        machine_fingerprint: str,
        agent_version: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/agents/register",
            json={
                "registration_token": registration_token,
                "local_identity": local_identity,
                "hostname": hostname,
                "name": name,
                "machine_fingerprint": machine_fingerprint,
                "agent_version": agent_version,
            },
        ).json()

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        return self._request("GET", f"/agents/{agent_id}").json()

    def list_agents(self) -> list[dict[str, Any]]:
        return self._request("GET", "/agents").json()

    def get_agent_capacity(self, agent_id: str) -> dict[str, Any]:
        return self._request("GET", f"/agents/{agent_id}/capacity").json()

    def disable_agent(self, agent_id: str, reason: str) -> dict[str, Any]:
        return self._request("POST", f"/agents/{agent_id}/disable", json={"reason": reason}).json()

    # -- executions --------------------------------------------------------

    def create_execution(
        self,
        automation_version_id: int,
        *,
        agent_id: str | None = None,
        parameters: dict[str, Any] | None = None,
        priority: int = 0,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "automation_version_id": automation_version_id,
            "parameters": parameters or {},
            "priority": priority,
        }
        if agent_id:
            payload["agent_id"] = agent_id
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._request("POST", "/executions", json=payload, headers=headers).json()

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        return self._request("GET", f"/executions/{execution_id}").json()

    def get_execution_tasks(self, execution_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/executions/{execution_id}/tasks").json()

    def get_execution_attempts(self, execution_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/executions/{execution_id}/attempts").json()

    def cancel_execution(self, execution_id: str) -> dict[str, Any]:
        return self._request("POST", f"/executions/{execution_id}/cancel").json()

    def get_execution_artifacts(self, execution_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/executions/{execution_id}/artifacts").json()
