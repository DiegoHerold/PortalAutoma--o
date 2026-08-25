"""Exercises PortalApiClient's request construction against a fake
transport (httpx.MockTransport) instead of a live Portal — these assert
"does this client send the request the real routes in
modules/*/api/routes.py expect", not "is the Portal actually running".
"""

from __future__ import annotations

import json

import httpx
import pytest

from tools.certification.api_client import PortalApiClient, PortalApiError


def _client_with_transport(transport: httpx.MockTransport) -> PortalApiClient:
    client = PortalApiClient(base_url="http://test/api/v1")
    client._client = httpx.Client(base_url="http://test/api/v1", transport=transport)
    return client


def test_login_sets_bearer_and_returns_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/login"
        body = json.loads(request.content)
        assert body == {"email": "admin@portal.local", "password": "admin123"}
        return httpx.Response(200, json={"access_token": "tok_123"})

    client = _client_with_transport(httpx.MockTransport(handler))
    token = client.login("admin@portal.local", "admin123")
    assert token == "tok_123"
    assert client._bearer == "tok_123"


def test_authorized_request_includes_bearer_header() -> None:
    seen_auth: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("authorization"))
        return httpx.Response(200, json=[])

    client = _client_with_transport(httpx.MockTransport(handler))
    client._bearer = "tok_abc"
    client.list_categories()
    assert seen_auth == ["Bearer tok_abc"]


def test_get_or_create_category_reuses_existing_by_slug() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": 7, "slug": "certification", "name": "Certification"}])
        raise AssertionError("should not POST when category already exists")

    client = _client_with_transport(httpx.MockTransport(handler))
    category = client.get_or_create_category("Certification", "certification")
    assert category["id"] == 7
    assert calls == ["GET"]


def test_get_or_create_category_creates_when_missing() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=[])
        body = json.loads(request.content)
        assert body["slug"] == "certification"
        return httpx.Response(201, json={"id": 9, **body})

    client = _client_with_transport(httpx.MockTransport(handler))
    category = client.get_or_create_category("Certification", "certification")
    assert category["id"] == 9
    assert calls == ["GET", "POST"]


def test_create_execution_omits_agent_id_when_not_pinned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "agent_id" not in body
        assert body["automation_version_id"] == 42
        assert request.headers.get("idempotency-key")
        return httpx.Response(201, json={"execution": {"id": "exe_1", "status": "pending"}})

    client = _client_with_transport(httpx.MockTransport(handler))
    result = client.create_execution(42, idempotency_key="k1")
    assert result["execution"]["id"] == "exe_1"


def test_error_response_raises_portal_api_error_with_status_and_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "Manifest is invalid."})

    client = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(PortalApiError) as exc_info:
        client.list_categories()
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {"detail": "Manifest is invalid."}
