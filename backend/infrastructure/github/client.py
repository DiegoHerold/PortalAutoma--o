"""GitHub App REST client used by Catalog and integration adapters."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import jwt

from infrastructure.config import get_settings


class GithubAppNotConfiguredError(Exception):
    pass


class GithubApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"GitHub API error ({status_code}): {message}")
        self.status_code = status_code


@dataclass(frozen=True)
class GithubRepository:
    id: int
    owner: str
    name: str
    full_name: str
    default_branch: str
    private: bool


@dataclass(frozen=True)
class GithubTreeEntry:
    path: str
    type: str
    sha: str


_installation_token_cache: dict[int, tuple[str, float]] = {}


class GithubAppClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.github_app_configured:
            raise GithubAppNotConfiguredError(
                "Integracao com GitHub nao configurada. Defina GITHUB_APP_ID e GITHUB_APP_PRIVATE_KEY."
            )
        self._http = httpx.Client(base_url=self.settings.github_api_base_url, timeout=30.0, trust_env=False)

    def _app_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": self.settings.github_app_id}
        private_key = self.settings.github_app_private_key.replace("\\n", "\n")
        return jwt.encode(payload, private_key, algorithm="RS256")

    def _installation_token(self, installation_id: int) -> str:
        cached = _installation_token_cache.get(installation_id)
        if cached and cached[1] > time.time() + 30:
            return cached[0]
        response = self._http.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {self._app_jwt()}", "Accept": "application/vnd.github+json"},
        )
        self._raise_for_status(response)
        data = response.json()
        token = data["token"]
        _installation_token_cache[installation_id] = (token, time.time() + 55 * 60)
        return token

    def _headers(self, installation_id: int) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._installation_token(installation_id)}", "Accept": "application/vnd.github+json"}

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                message = response.json().get("message", response.text)
            except Exception:
                message = response.text
            raise GithubApiError(response.status_code, message)

    def install_url(self) -> str:
        if not self.settings.github_app_slug:
            raise GithubAppNotConfiguredError("GITHUB_APP_SLUG nao configurado.")
        return f"https://github.com/apps/{self.settings.github_app_slug}/installations/new"

    def get_installation(self, installation_id: int) -> dict[str, Any]:
        response = self._http.get(
            f"/app/installations/{installation_id}",
            headers={"Authorization": f"Bearer {self._app_jwt()}", "Accept": "application/vnd.github+json"},
        )
        self._raise_for_status(response)
        return response.json()

    def list_repositories(self, installation_id: int) -> list[GithubRepository]:
        repos: list[GithubRepository] = []
        page = 1
        while True:
            response = self._http.get(
                "/installation/repositories",
                params={"per_page": 100, "page": page},
                headers=self._headers(installation_id),
            )
            self._raise_for_status(response)
            data = response.json()
            for repo in data.get("repositories", []):
                repos.append(
                    GithubRepository(
                        id=repo["id"],
                        owner=repo["owner"]["login"],
                        name=repo["name"],
                        full_name=repo["full_name"],
                        default_branch=repo.get("default_branch", "main"),
                        private=repo.get("private", True),
                    )
                )
            if len(data.get("repositories", [])) < 100:
                break
            page += 1
        return repos

    def list_branches(self, installation_id: int, owner: str, repo: str) -> list[str]:
        response = self._http.get(
            f"/repos/{owner}/{repo}/branches",
            params={"per_page": 100},
            headers=self._headers(installation_id),
        )
        self._raise_for_status(response)
        return [branch["name"] for branch in response.json()]

    def get_file_content(self, installation_id: int, owner: str, repo: str, path: str, ref: str) -> str:
        response = self._http.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
            headers=self._headers(installation_id),
        )
        self._raise_for_status(response)
        data = response.json()
        if data.get("encoding") != "base64":
            raise GithubApiError(500, f"Encoding inesperado para {path}: {data.get('encoding')}")
        return base64.b64decode(data["content"]).decode("utf-8")

    def get_latest_commit_sha(self, installation_id: int, owner: str, repo: str, ref: str) -> str:
        response = self._http.get(f"/repos/{owner}/{repo}/commits/{ref}", headers=self._headers(installation_id))
        self._raise_for_status(response)
        return response.json()["sha"]

    def get_latest_commit_for_path(self, installation_id: int, owner: str, repo: str, branch: str, path: str) -> str | None:
        response = self._http.get(
            f"/repos/{owner}/{repo}/commits",
            params={"sha": branch, "path": path, "per_page": 1},
            headers=self._headers(installation_id),
        )
        self._raise_for_status(response)
        commits = response.json()
        return commits[0]["sha"] if commits else None

    def list_repository_tree(self, installation_id: int, owner: str, repo: str, ref: str) -> list[GithubTreeEntry]:
        commit_sha = self.get_latest_commit_sha(installation_id, owner, repo, ref)
        response = self._http.get(
            f"/repos/{owner}/{repo}/git/trees/{commit_sha}",
            params={"recursive": "1"},
            headers=self._headers(installation_id),
        )
        self._raise_for_status(response)
        data = response.json()
        if data.get("truncated"):
            raise GithubApiError(500, "A arvore do repositorio e grande demais para listar em uma unica chamada.")
        return [
            GithubTreeEntry(path=item["path"], type=item["type"], sha=item["sha"])
            for item in data.get("tree", [])
            if item["type"] in ("blob", "tree")
        ]

    def get_blob(self, installation_id: int, owner: str, repo: str, sha: str) -> bytes:
        response = self._http.get(f"/repos/{owner}/{repo}/git/blobs/{sha}", headers=self._headers(installation_id))
        self._raise_for_status(response)
        data = response.json()
        if data.get("encoding") != "base64":
            raise GithubApiError(500, f"Encoding inesperado para blob {sha}: {data.get('encoding')}")
        return base64.b64decode(data["content"])

    def download_directory(self, installation_id: int, owner: str, repo: str, ref: str, dir_path: str, destination: Path) -> None:
        tree = self.list_repository_tree(installation_id, owner, repo, ref)
        prefix = dir_path.rstrip("/") + "/"
        matched = [item for item in tree if item.type == "blob" and (item.path == dir_path or item.path.startswith(prefix))]
        if not matched:
            raise GithubApiError(404, f"Nenhum arquivo encontrado em {dir_path}.")
        for entry in matched:
            relative = entry.path[len(prefix) :] if entry.path.startswith(prefix) else entry.path
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.get_blob(installation_id, owner, repo, entry.sha))

    def close(self) -> None:
        self._http.close()


def verify_webhook_signature(payload_body: bytes, signature_header: str | None, secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)
