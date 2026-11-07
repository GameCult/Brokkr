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

    def test_token_is_stripped_before_the_store_sees_the_message(self):
        for message in (PUT, DELETE):
            self.call({**message, sg.TOKEN_FIELD: self.guard.token})
        self.assertEqual(len(self.server.handled), 2)
        for handled in self.server.handled:
            self.assertNotIn(sg.TOKEN_FIELD, handled)

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

    def test_stop_server_revokes_and_purges_even_when_the_socket_stop_raises(self):
        target = bt.BrokkrBlenderTarget(types.SimpleNamespace())

        def boom():
            raise OSError("close failed")
        target._server = types.SimpleNamespace(stop=boom)
        target._guard = sg.SessionGuard()
        guard = target._guard
        old = guard.token
        target._node = FakeNode(["c1"])
        target._documents = {"command_intent": "DOC"}
        with self.assertRaises(OSError):
            target.stop_server()
        self.assertFalse(guard.admits({sg.TOKEN_FIELD: old}))
        self.assertEqual(target._node.database.keys, [])
        self.assertIsNone(target._server)

    def test_enforce_bind_policy_stops_only_a_non_loopback_server_without_the_allow(self):
        for host, allow, stays in (("0.0.0.0", False, False), ("0.0.0.0", True, True), ("127.0.0.1", False, True)):
            target = bt.BrokkrBlenderTarget(types.SimpleNamespace())
            target._server = types.SimpleNamespace(host=host, stop=lambda: None)
            target.enforce_bind_policy(allow)
            self.assertEqual(target._server is not None, stays, (host, allow))

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
        self.assertTrue(status["cultmeshModule"].endswith("__init__.py"))
        self.assertIn("cultmesh_py", status["cultmeshModule"])
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

    def test_a_peer_put_is_accepted_over_tcp_because_the_target_grants_peer_writes(self):
        status = self.start()
        cultmesh, _ = bt._load_cultmesh(PACKAGES)
        import cultnet_py
        document = self.target._documents["command_intent"]
        client = cultmesh.CultMesh.create_client("127.0.0.1", status["port"], timeout_seconds=3.0)
        with client.subscribe_database(subscription_id="peer", schema_ids=[bt.COMMAND_INTENT_SCHEMA],
                                       include_snapshot=False) as subscription:
            subscription.send(cultnet_py.document_put_raw(
                message_id="peer-put", key="blender/commands/peer", schema_id=document.catalog_entry().schema_id,
                stored_at="2026-11-07T00:00:00Z",
                payload=document.encode_payload({
                    "schema": bt.COMMAND_INTENT_SCHEMA, "commandId": "peer", "action": "createObject"}),
            ))
            change = subscription.read_next_change()  # a refusal would raise CultNetPeerError instead
        self.assertEqual(change.record_key, "blender/commands/peer")

    def queue_intent(self, key="blender/commands/q1"):
        node, documents = self.target._open_node(self.cache, PACKAGES)
        node.database.put(documents["command_intent"], key, {
            "schema": bt.COMMAND_INTENT_SCHEMA, "commandId": "q1", "action": "createObject"})
        return node, documents

    def queued(self, cache_path):
        """Intent keys in the .ccmp as a fresh node reads it from disk."""
        cultmesh, cultcache = bt._load_cultmesh(PACKAGES)
        fresh = cultmesh.CultMesh.start_node(cache_path, runtime_id="reader")
        fresh.database.register_document(cultcache.define_document_type(bt.COMMAND_INTENT_SCHEMA))
        fresh.database.pull()
        return list(fresh.database.snapshot().get(bt.COMMAND_INTENT_SCHEMA, {}))

    def test_start_purges_intents_queued_in_the_node_and_they_stay_gone_after_reopening(self):
        self.queue_intent()
        self.assertEqual(len(self.queued(self.cache)), 1)
        self.start()
        node, _ = self.target._open_node(self.cache, PACKAGES)
        self.assertEqual(list(node.database.snapshot().get(bt.COMMAND_INTENT_SCHEMA, {})), [])
        self.assertEqual(self.queued(self.cache), [])

    def test_stop_purges_intents_queued_while_running_and_they_stay_gone_after_reopening(self):
        self.start()
        self.queue_intent()
        self.target.stop_server()
        self.assertEqual(self.queued(self.cache), [])

    def test_allow_true_goes_through_start_server_and_unticking_stops_it(self):
        status = self.target.start_server(self.cache, PACKAGES, "0.0.0.0", 0, 100, 1 << 20, self.debug,
                                          allow_non_loopback=True)
        self.assertTrue(status["running"])
        self.assertFalse(status["loopback"])
        with self.assertRaises(sg.BindRefused):
            self.target.start_server(self.cache, PACKAGES, "0.0.0.0", 0, 100, 1 << 20, self.debug,
                                     allow_non_loopback=False)
        self.assertFalse(self.target.server_status()["running"])

    def test_unticking_the_allow_stops_a_running_non_loopback_server(self):
        self.target.start_server(self.cache, PACKAGES, "0.0.0.0", 0, 100, 1 << 20, self.debug,
                                 allow_non_loopback=True)
        self.target.enforce_bind_policy(False)
        self.assertFalse(self.target.server_status()["running"])

    def test_a_put_with_a_shard_id_and_a_valid_token_leaves_no_token_in_the_shard_log_or_store(self):
        import msgpack
        status = self.start(require_token=True)
        token = self.target.session_token
        node, documents = self.target._open_node(self.cache, PACKAGES)
        cultmesh, cultcache = bt._load_cultmesh(PACKAGES)
        scratch = cultmesh.CultMesh.start_node(str(Path(self.tmp.name) / "scratch.ccmp"), runtime_id="scratch")
        scratch.database.register_document(cultcache.define_document_type(bt.COMMAND_INTENT_SCHEMA))
        built = scratch.database.put_raw_message(
            cultcache.define_document_type(bt.COMMAND_INTENT_SCHEMA), "blender/commands/s1",
            {"schema": bt.COMMAND_INTENT_SCHEMA, "commandId": "s1", "action": "createObject"},
            message_id="m1", shard_id="shard-a", shard_epoch=1)
        wire = built.to_wire()
        wire[sg.TOKEN_FIELD] = token
        server = self.target._server
        responses = server._handle_connection_message(wire, {})
        self.assertNotEqual(responses and responses[0].get("schemaVersion"), "cultnet.error.v0", responses)
        log = node.database.create_shard_log_response(shard_id="shard-a", shard_epoch=1)
        self.assertIn("s1", repr(log))
        self.assertNotIn(token, repr(log))
        self.assertNotIn(sg.TOKEN_FIELD, repr(log))
        self.assertNotIn(token, repr(node.database.snapshot()))
        self.assertNotIn(token.encode(), msgpack.packb(log, use_bin_type=True))

    def test_a_delete_with_a_shard_id_and_a_valid_token_leaves_no_token_in_the_shard_log(self):
        import msgpack
        self.start(require_token=True)
        token = self.target.session_token
        node, _ = self.target._open_node(self.cache, PACKAGES)
        cultmesh, cultcache = bt._load_cultmesh(PACKAGES)
        scratch = cultmesh.CultMesh.start_node(str(Path(self.tmp.name) / "scratch2.ccmp"), runtime_id="scratch2")
        document = cultcache.define_document_type(bt.COMMAND_INTENT_SCHEMA)
        scratch.database.register_document(document)
        put = scratch.database.put_raw_message(
            document, "blender/commands/d1",
            {"schema": bt.COMMAND_INTENT_SCHEMA, "commandId": "d1", "action": "createObject"},
            message_id="m1", shard_id="shard-b", shard_epoch=1)
        delete = scratch.database.delete_raw_message(document, "blender/commands/d1", message_id="m2",
                                                     shard_id="shard-b", shard_epoch=1)
        server = self.target._server
        for message in (put, delete):
            wire = message.to_wire()
            wire[sg.TOKEN_FIELD] = token
            responses = server._handle_connection_message(wire, {})
            self.assertFalse([r for r in responses if r.get("schemaVersion") == "cultnet.error.v0"], responses)
        log = node.database.create_shard_log_response(shard_id="shard-b", shard_epoch=1)
        self.assertIn("document_delete", repr(log))
        self.assertNotIn(sg.TOKEN_FIELD, repr(log))
        self.assertNotIn(token.encode(), msgpack.packb(log, use_bin_type=True))

    def test_non_loopback_bind_is_refused_before_anything_starts(self):
        with self.assertRaises(sg.BindRefused):
            self.target.start_server(self.cache, PACKAGES, "0.0.0.0", 0, 100, 1 << 20, self.debug)
        self.assertFalse(self.target.server_status()["running"])


if __name__ == "__main__":
    unittest.main()
