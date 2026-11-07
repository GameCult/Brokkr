"""Add-on UI wiring tests with a fake bpy: preference callbacks, the copy operator, the panel.

The add-on's __init__ is loaded as package "brokkr_addon" against a fake bpy module whose
property constructors record their arguments. Blender itself is not run.
"""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ADDON = Path(__file__).resolve().parents[1] / "brokkr_bridge"
NS = types.SimpleNamespace


class Prop:
    def __init__(self, kind, **kwargs):
        self.kind, self.kwargs = kind, kwargs


class Base:
    def report(self, level, message):
        self.reported = (level, message)


def load_addon():
    props = NS(**{k: (lambda kind: lambda **kw: Prop(kind, **kw))(k)
                  for k in ("StringProperty", "BoolProperty", "IntProperty")})
    fake = types.ModuleType("bpy")
    fake.types = NS(AddonPreferences=Base, Panel=Base, Operator=Base)
    fake.props = props
    fake.app = NS(handlers=NS(depsgraph_update_post=[]), timers=NS(is_registered=lambda f: False))
    fake.utils = NS()
    previous = sys.modules.get("bpy")
    sys.modules["bpy"] = fake
    try:
        spec = importlib.util.spec_from_file_location("brokkr_addon", ADDON / "__init__.py",
                                                      submodule_search_locations=[str(ADDON)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["brokkr_addon"] = module
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            del sys.modules["bpy"]
        else:
            sys.modules["bpy"] = previous
    return module


addon = load_addon()
from brokkr_addon import blender_target as bt  # noqa: E402
from brokkr_addon import server_guard as sg  # noqa: E402


def running_target(host="0.0.0.0", token=True):
    target = bt.BrokkrBlenderTarget(NS(path=NS(abspath=lambda p: p)))
    target._server = NS(host=host, port=4321, stop=lambda: None)
    target._guard = sg.SessionGuard() if token else None
    target._node = None
    target._cultmesh_module = "/x/cultmesh_py/__init__.py"
    return target


class PreferenceTests(unittest.TestCase):
    def prop(self, name):
        return addon.BrokkrPreferences.__annotations__[name]

    def test_allow_non_loopback_defaults_off_and_carries_an_update_callback(self):
        prop = self.prop("allow_non_loopback")
        self.assertIs(prop.kwargs["default"], False)
        self.assertTrue(callable(prop.kwargs.get("update")))

    def test_the_update_callback_stops_a_running_non_loopback_server_when_unticked(self):
        addon._target = running_target("0.0.0.0")
        self.prop("allow_non_loopback").kwargs["update"](NS(allow_non_loopback=False), None)
        self.assertIsNone(addon._target._server)

    def test_the_update_callback_leaves_the_server_when_ticked_or_loopback(self):
        for host, allow in (("0.0.0.0", True), ("127.0.0.1", False)):
            addon._target = running_target(host)
            self.prop("allow_non_loopback").kwargs["update"](NS(allow_non_loopback=allow), None)
            self.assertIsNotNone(addon._target._server, (host, allow))

    def test_the_session_token_preference_defaults_off(self):
        self.assertIs(self.prop("require_session_token").kwargs["default"], False)


class CopyOperatorTests(unittest.TestCase):
    def run_copy(self, target):
        addon._target = target
        window_manager = NS(clipboard="")
        operator = addon.BROKKR_OT_copy_session_token()
        result = operator.execute(NS(window_manager=window_manager))
        return result, window_manager.clipboard, operator.reported

    def test_copies_the_running_token_to_the_clipboard(self):
        target = running_target()
        result, clipboard, reported = self.run_copy(target)
        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(clipboard, target.session_token)
        self.assertNotIn(target.session_token, reported[1])

    def test_without_a_token_it_copies_nothing(self):
        for target in (running_target(token=False), bt.BrokkrBlenderTarget(NS())):
            result, clipboard, _ = self.run_copy(target)
            self.assertEqual(result, {"CANCELLED"})
            self.assertEqual(clipboard, "")

    def test_the_operator_is_registered(self):
        self.assertIn(addon.BROKKR_OT_copy_session_token, addon.classes)


class PanelTests(unittest.TestCase):
    def test_the_panel_never_draws_the_token(self):
        target = running_target()
        addon._target = target
        layout = mock.MagicMock()
        panel = addon.BROKKR_PT_status()
        panel.layout = layout
        prefs = mock.MagicMock()
        context = NS(preferences=NS(addons={"brokkr_addon": NS(preferences=prefs)}))
        panel.draw(context)
        texts = [str(c.kwargs.get("text", "")) for c in layout.mock_calls if c.kwargs]
        self.assertFalse([t for t in texts if target.session_token in t])
        operators = [c.args[0] for c in layout.operator.mock_calls]
        self.assertIn("brokkr.copy_session_token", operators)
        self.assertTrue([t for t in texts if "WARNING" in t or "cultmesh_py loaded from" in t])


if __name__ == "__main__":
    unittest.main()
