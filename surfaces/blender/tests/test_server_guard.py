"""Server hardening tests. No Blender: the add-on package is registered without running its
__init__ (which imports bpy), so only server_guard and blender_target load.

Run: python3 -m unittest discover -s surfaces/blender/tests -v
The real-server tests need CultLib's Python packages: set CULTLIB_PACKAGES to the packages
directory, or they are skipped.
"""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ADDON = Path(__file__).resolve().parents[1] / "brokkr_bridge"
package = types.ModuleType("brokkr_bridge")
package.__path__ = [str(ADDON)]
sys.modules.setdefault("brokkr_bridge", package)

from brokkr_bridge import server_guard as sg  # noqa: E402
from brokkr_bridge import blender_target as bt  # noqa: E402

PUT = {"schemaVersion": "cultnet.document_put_raw.v0", "messageId": "m1", "document": {}}
DELETE = {"schemaVersion": "cultnet.document_delete.v0", "messageId": "m2"}
SUBSCRIBE = {"schemaVersion": "cultnet.database_subscribe.v0", "messageId": "m3"}


class FakeBase:
    def __init__(self):
        self.handled = []

    @staticmethod
    def _error_response(error, *, message_id="", code=None, details=None):
        response = {"schemaVersion": "cultnet.error.v0", "messageId": message_id, "error": error}
        if code is not None:
            response["code"] = code
        return response

    def _handle_connection_message(self, message, subscriptions, *, over_rudp=False):
        self.handled.append(message)
        return [{"schemaVersion": "handled"}]


class SessionGuardTests(unittest.TestCase):
    def test_token_is_random_and_unguessable(self):
        tokens = {sg.SessionGuard().token for _ in range(50)}
        self.assertEqual(len(tokens), 50)
        self.assertGreaterEqual(min(len(t) for t in tokens), 32)

    def test_admits_only_the_exact_token(self):
        guard = sg.SessionGuard()
        self.assertTrue(guard.admits({sg.TOKEN_FIELD: guard.token}))
        self.assertFalse(guard.admits({}))
        self.assertFalse(guard.admits({sg.TOKEN_FIELD: ""}))
        self.assertFalse(guard.admits({sg.TOKEN_FIELD: guard.token + "x"}))
        self.assertFalse(guard.admits({sg.TOKEN_FIELD: guard.token[:-1]}))
        self.assertFalse(guard.admits({sg.TOKEN_FIELD: 12345}))
        self.assertFalse(guard.admits({sg.TOKEN_FIELD: None}))

    def test_revoke_rejects_the_old_token_and_the_empty_one(self):
        guard = sg.SessionGuard()
        old = guard.token
        guard.revoke()
        self.assertFalse(guard.admits({sg.TOKEN_FIELD: old}))
        self.assertFalse(guard.admits({sg.TOKEN_FIELD: ""}))
        self.assertEqual(guard.token, "")


class GuardedServerTests(unittest.TestCase):
    def setUp(self):
        self.guard = sg.SessionGuard()
        self.server = sg.guarded_server_class(FakeBase, self.guard)()

    def call(self, message):
        return self.server._handle_connection_message(message, {})

    def test_put_and_delete_without_token_are_refused_and_never_reach_the_store(self):
        for message in (PUT, DELETE):
            response = self.call(message)
            self.assertEqual(response[0]["schemaVersion"], "cultnet.error.v0")
            self.assertNotIn("code", response[0])
            self.assertEqual(response[0]["messageId"], message["messageId"])
        self.assertEqual(self.server.handled, [])

    def test_token_is_checked_on_every_put_not_only_the_first(self):
        good = {**PUT, sg.TOKEN_FIELD: self.guard.token}
        self.assertEqual(self.call(good)[0]["schemaVersion"], "handled")
        self.assertEqual(self.call(PUT)[0]["schemaVersion"], "cultnet.error.v0")
        self.assertEqual(self.call(good)[0]["schemaVersion"], "handled")
        self.assertEqual(self.call({**PUT, sg.TOKEN_FIELD: "wrong"})[0]["schemaVersion"], "cultnet.error.v0")
        self.assertEqual(len(self.server.handled), 2)

    def test_reads_need_no_token(self):
        self.assertEqual(self.call(SUBSCRIBE)[0]["schemaVersion"], "handled")

    def test_revoked_token_stops_working_on_a_running_server(self):
        good = {**PUT, sg.TOKEN_FIELD: self.guard.token}
        self.guard.revoke()
        self.assertEqual(self.call(good)[0]["schemaVersion"], "cultnet.error.v0")


class BindTests(unittest.TestCase):
    def test_loopback_hosts_bind_without_the_allow(self):
        for host in ("", "127.0.0.1", "127.0.0.2", "::1", "localhost", "LOCALHOST"):
            self.assertEqual(sg.check_bind(host, False), host or "127.0.0.1")

    def test_non_loopback_hosts_are_refused_without_the_allow(self):
        for host in ("0.0.0.0", "::", "192.168.1.5", "10.0.0.1", "example.com"):
            with self.assertRaises(sg.BindRefused):
                sg.check_bind(host, False)

    def test_the_allow_lets_a_non_loopback_host_through(self):
        self.assertEqual(sg.check_bind("0.0.0.0", True), "0.0.0.0")
        self.assertFalse(sg.is_loopback_host("0.0.0.0"))


class FakeDatabase:
    def __init__(self, schema, keys):
        self.schema, self.keys, self.deleted, self.pulls = schema, list(keys), [], 0

    def pull(self):
        self.pulls += 1

    def snapshot(self):
        return {self.schema: {k: {} for k in self.keys}, "other.v0": {"keep": {}}}

    def delete(self, document, key):
        self.deleted.append((document, key))
        self.keys.remove(key)


class FakeNode:
    def __init__(self, keys):
        self.database = FakeDatabase(bt.COMMAND_INTENT_SCHEMA, keys)


class PurgeTests(unittest.TestCase):
    def make_debug_root(self, tmp):
        commands = Path(tmp) / "blender" / "commands"
        commands.mkdir(parents=True)
        (commands / "a.json").write_text("{}")
        (commands / "b.json").write_text("{}")
        (commands / "note.txt").write_text("keep")
        receipts = Path(tmp) / "blender" / "receipts"
        receipts.mkdir()
        (receipts / "r.json").write_text("{}")
        return commands, receipts

    def test_purge_removes_queued_intents_and_debug_command_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands, receipts = self.make_debug_root(tmp)
            node = FakeNode(["c1", "c2"])
            removed = sg.purge_command_intents(node, "DOC", bt.COMMAND_INTENT_SCHEMA, tmp)
            self.assertEqual(removed, 4)
            self.assertEqual(node.database.deleted, [("DOC", "c1"), ("DOC", "c2")])
            self.assertEqual(sorted(p.name for p in commands.iterdir()), ["note.txt"])
            self.assertTrue((receipts / "r.json").exists())

    def test_purge_without_a_debug_root_or_node_is_quiet(self):
        self.assertEqual(sg.purge_command_intents(None, "DOC", bt.COMMAND_INTENT_SCHEMA, ""), 0)

    def test_stop_server_purges_and_revokes(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands, _ = self.make_debug_root(tmp)
            target = bt.BrokkrBlenderTarget(types.SimpleNamespace())
            stopped = []
            target._server = types.SimpleNamespace(stop=lambda: stopped.append(True))
            target._guard = sg.SessionGuard()
            guard = target._guard
            old = guard.token
            target._node = FakeNode(["c1"])
            target._documents = {"command_intent": "DOC"}
            target._debug_mirror_root = tmp
            target.stop_server()
            self.assertEqual(stopped, [True])
            self.assertEqual(target._node.database.keys, [])
            self.assertEqual(sorted(p.name for p in commands.iterdir()), ["note.txt"])
            self.assertFalse(guard.admits({sg.TOKEN_FIELD: old}))
            self.assertEqual(target.session_token, "")

    def test_stop_server_with_no_server_running_purges_nothing(self):
        target = bt.BrokkrBlenderTarget(types.SimpleNamespace())
        target._node = FakeNode(["c1"])
        target._documents = {"command_intent": "DOC"}
        target.stop_server()
        self.assertEqual(target._node.database.keys, ["c1"])


PACKAGES = os.environ.get("CULTLIB_PACKAGES", "")


@unittest.skipUnless(PACKAGES and Path(PACKAGES).is_dir(), "set CULTLIB_PACKAGES to CultLib's packages directory")
class RealServerTests(unittest.TestCase):
    """The target's start_server against cultmesh_py's real server: token on, token off, bind refusal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.debug = str(Path(self.tmp.name) / "debug")
        commands = Path(self.debug) / "blender" / "commands"
        commands.mkdir(parents=True)
        (commands / "stale.json").write_text("{}")
        self.cache = str(Path(self.tmp.name) / "node.ccmp")
        self.target = bt.BrokkrBlenderTarget(types.SimpleNamespace(
            path=types.SimpleNamespace(abspath=lambda p: p)))
        self.addCleanup(self.target.stop_server)

    def start(self, **kwargs):
        return self.target.start_server(self.cache, PACKAGES, "127.0.0.1", 0, 100, 1 << 20, self.debug, **kwargs)

    def test_default_start_has_no_token_and_purges_stale_debug_commands(self):
        status = self.start()
        self.assertTrue(status["running"])
        self.assertFalse(status["tokenRequired"])
        self.assertEqual(self.target.session_token, "")
        self.assertEqual(list((Path(self.debug) / "blender" / "commands").glob("*.json")), [])
        self.assertEqual(status["cultlibPySrc"], str(Path(PACKAGES)))
        self.assertTrue(status["loopback"])

    def test_token_on_refuses_unauthenticated_put_on_the_real_server(self):
        status = self.start(require_token=True)
        self.assertTrue(status["tokenRequired"])
        server = self.target._server
        message = {"schemaVersion": "cultnet.document_put_raw.v0", "messageId": "x", "document": {}}
        self.assertEqual(server._handle_connection_message(message, {})[0]["schemaVersion"], "cultnet.error.v0")
        message[sg.TOKEN_FIELD] = self.target.session_token
        response = server._handle_connection_message(message, {})
        self.assertIn("malformed", response[0].get("code", ""))  # past the guard, refused by the store as an empty put

    def test_non_loopback_bind_is_refused_before_anything_starts(self):
        with self.assertRaises(sg.BindRefused):
            self.target.start_server(self.cache, PACKAGES, "0.0.0.0", 0, 100, 1 << 20, self.debug)
        self.assertFalse(self.target.server_status()["running"])


if __name__ == "__main__":
    unittest.main()
