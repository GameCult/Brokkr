"""Server hardening for the Blender add-on's CultMesh server.

Stdlib only, no bpy: everything here is unit-testable without Blender.

Always on: a non-loopback bind needs an explicit allow (check_bind), and command
intents queued before a start or stop are purged (purge_command_intents).
Opt-in: a per-session token, checked on every document put and delete when the
user turns it on in the add-on preferences (SessionGuard, guarded_server_class).
"""
from __future__ import annotations

import hmac
import ipaddress
import secrets
from pathlib import Path
from typing import Any

PUT_SCHEMA_VERSIONS = ("cultnet.document_put_raw.v0", "cultnet.document_delete.v0")
TOKEN_FIELD = "sessionToken"
LOOPBACK_HOSTNAMES = ("localhost",)


class BindRefused(ValueError):
    """A non-loopback bind was requested without the explicit allow."""


def is_loopback_host(host: str) -> bool:
    """An empty host means the default 127.0.0.1. A hostname other than localhost is not
    resolved and counts as non-loopback, so the allow is needed."""
    host = (host or "127.0.0.1").strip()
    if host.lower() in LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_bind(host: str, allow_non_loopback: bool) -> str:
    """Return the host to bind, or raise BindRefused for a non-loopback host without the allow."""
    resolved = (host or "127.0.0.1").strip()
    if not is_loopback_host(resolved) and not allow_non_loopback:
        raise BindRefused(
            f"Refusing to bind {resolved!r}: not a loopback address. Tick 'Allow Non-Loopback Bind' "
            "in the add-on preferences to serve beyond this machine."
        )
    return resolved


class SessionGuard:
    """The per-session token. Held in memory only; never written to preferences or the cache."""

    def __init__(self) -> None:
        self._token: str | None = secrets.token_urlsafe(32)

    @property
    def token(self) -> str:
        return self._token or ""

    def revoke(self) -> None:
        self._token = None

    def admits(self, message: dict[str, Any]) -> bool:
        presented = message.get(TOKEN_FIELD)
        if self._token is None or not isinstance(presented, str):
            return False
        return hmac.compare_digest(presented.encode("utf-8"), self._token.encode("utf-8"))


def guarded_server_class(base: type, guard: SessionGuard) -> type:
    """A subclass of cultmesh_py's CultMeshLocalServer whose puts and deletes need the guard's token.

    CultMeshLocalServer sends every connection message, TCP and RUDP, through
    _handle_connection_message, which is where the check sits. Reads (snapshot, subscribe,
    hello) stay open. The refusal is codeless: cultnet.error.v0's code list is closed and
    this adds no code to it."""

    class GuardedServer(base):  # type: ignore[misc, valid-type]
        def _handle_connection_message(self, message, subscriptions, **kwargs):
            if message.get("schemaVersion") in PUT_SCHEMA_VERSIONS and not guard.admits(message):
                return [self._error_response(
                    f"Document writes need the session token in the {TOKEN_FIELD} field.",
                    message_id=str(message.get("messageId") or ""),
                )]
            if TOKEN_FIELD in message:
                # The store copies every envelope field but schemaVersion into the shard log it
                # serves, so the token must not reach it.
                message = {key: value for key, value in message.items() if key != TOKEN_FIELD}
            return super()._handle_connection_message(message, subscriptions, **kwargs)

    return GuardedServer


def purge_command_intents(node: Any, command_document: Any, command_schema: str, debug_mirror_root: str) -> int:
    """Delete every queued command intent from the node and every command JSON under
    <debug_mirror_root>/blender/commands. Returns how many were removed."""
    removed = 0
    if node is not None:
        node.database.pull()
        for key in list(node.database.snapshot().get(command_schema, {})):
            node.database.delete(command_document, key)
            removed += 1
    if debug_mirror_root:
        for path in (Path(debug_mirror_root) / "blender" / "commands").glob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
    return removed
