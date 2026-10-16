import copy
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

from swm_core.world import World
from swm_core.scenarios import create
from swm_core.session import Session
from swm_core.learning import LocalTransitionModel
from swm_workbench.server import Workbench


class WorldTests(unittest.TestCase):
    def test_water_is_conserved_and_nonnegative_under_four_outflows(self):
        w = create("blank")
        w.apply({"kind": "water", "x": 10, "y": 10, "amount": 0.001})
        w.apply({"kind": "set", "x": 10, "y": 10, "field": "elevation", "value": 10})
        for _ in range(5):
            w.step(100)
        self.assertAlmostEqual(w.water.sum(), 0.001, places=10)
        self.assertGreaterEqual(w.water.min(), 0)

    def test_lake_injection_can_leave_glyph_unchanged(self):
        w = create("water")
        before = w.glyphs()
        total = w.water.sum()
        w.apply({"kind": "water", "x": 22, "y": 16, "amount": 0.3})
        self.assertEqual(before, w.glyphs())
        self.assertAlmostEqual(w.water.sum(), total + 0.3)
        w.step(100)
        self.assertAlmostEqual(w.stats()["water_error"], 0, places=9)

    def test_door_changes_connectivity_and_actor_movement(self):
        w = create("room")
        self.assertEqual(len(w.rooms()), 1)
        w.apply({"kind": "paint", "x": 10, "y": 7, "glyph": "人"})
        w.apply({"kind": "move", "dx": 1, "dy": 0})
        self.assertEqual(w.actor, [10, 7])
        w.apply({"kind": "door", "x": 11, "y": 7})
        self.assertEqual(len(w.rooms()), 0)
        w.apply({"kind": "move", "dx": 1, "dy": 0})
        self.assertEqual(w.actor, [11, 7])
        with self.assertRaises(ValueError):
            w.apply({"kind": "door", "x": 11, "y": 7})

    def test_wet_material_and_oxygen_intervention_change_outcome(self):
        w = create("fire")
        w.step(100)
        self.assertLess(w.fuel[8:12, 6:8].sum(), w.fuel[8:12, 15:17].sum())
        self.assertGreater(w.char[8:12, 24:26].sum(), w.char[8:12, 6:8].sum())
        self.assertAlmostEqual(w.stats()["material_error"], 0, places=9)

    def test_water_cools_identically_heated_material(self):
        dry, wet = create("blank"), create("blank")
        for w in (dry, wet):
            w.apply({"kind": "paint", "x": 5, "y": 5, "glyph": "木"})
            w.apply({"kind": "paint", "x": 5, "y": 5, "glyph": "火"})
        wet.apply({"kind": "water", "x": 5, "y": 5, "amount": 2})
        dry.step(10)
        wet.step(10)
        self.assertLess(wet.temperature[5, 5], dry.temperature[5, 5])

    def test_ignored_cell_retains_hidden_amount(self):
        w = create("water")
        amount = w.water[16, 22]
        w.apply({"kind": "paint", "x": 22, "y": 16, "glyph": "，"})
        self.assertEqual(w.glyphs()[16][22], "，")
        self.assertEqual(w.water[16, 22], amount)
        self.assertNotIn("fields", w.observation())
        self.assertNotIn("events", w.observation())

    def test_invalid_command_is_atomic(self):
        w = create()
        digest = w.digest()
        for c in ({"kind": "water", "x": 2, "y": 2, "amount": 1},
                  {"kind": "set", "x": 5, "y": 5, "field": "temperature", "value": float("nan")},
                  {"kind": "paint", "x": 3, "y": 4, "glyph": "墙"}):
            with self.assertRaises(ValueError):
                w.apply(c)
            self.assertEqual(w.digest(), digest)

    def test_material_edit_has_explicit_source_and_sink(self):
        w = create("blank")
        w.apply({"kind": "paint", "x": 5, "y": 5, "glyph": "木"})
        w.apply({"kind": "paint", "x": 5, "y": 5, "glyph": "火"})
        w.step(50)
        w.apply({"kind": "paint", "x": 5, "y": 5, "glyph": "土"})
        self.assertAlmostEqual(w.stats()["material_error"], 0, places=10)

    def test_restore_rejects_wrong_shape_nan_and_version(self):
        data = create().snapshot()
        for mutate in (lambda d: d["fields"]["water"].pop(),
                       lambda d: d["fields"]["temperature"][0].__setitem__(0, float("nan")),
                       lambda d: d.__setitem__("version", "999")):
            bad = copy.deepcopy(data)
            mutate(bad)
            with self.assertRaises(ValueError):
                World.restore(bad)

    def test_restore_rejects_wrapped_material_ids_and_malformed_events(self):
        s = Session("blank")
        original = s.world.digest()
        for events in ([None], [{"tick": 0}], [{"tick": 1, "kind": "编辑", "detail": "", "x": 2, "y": 2}]):
            replay = s.export()
            replay["initial"]["events"] = events
            with self.assertRaises(ValueError):
                s.load(replay)
            self.assertEqual(s.world.digest(), original)
        bad = s.world.snapshot()
        bad["fields"]["ground"][0][0] = 65536
        with self.assertRaises(ValueError):
            World.restore(bad)

    def test_replay_and_branching_reproduce_exact_state(self):
        s = Session("water")
        s.action({"kind": "water", "x": 22, "y": 16, "amount": 0.5})
        s.step(30)
        s.step(20)
        s.seek(1)
        s.action({"kind": "set", "x": 22, "y": 16, "field": "elevation", "value": 1})
        s.step(40)
        imported = Session()
        imported.load(json.loads(json.dumps(s.export())))
        self.assertEqual(s.world.digest(), imported.world.digest())
        self.assertEqual(len(s.operations), 3)

    def test_tampered_replay_does_not_replace_session(self):
        s = Session()
        original = s.world.digest()
        replay = s.export()
        replay["final_hash"] = "bad"
        with self.assertRaises(ValueError):
            s.load(replay)
        self.assertEqual(original, s.world.digest())

    def test_history_is_bounded_but_replay_preserves_all_operations(self):
        s = Session("blank")
        for _ in range(245):
            s.step()
        self.assertEqual(len(s.frames), 241)
        imported = Session()
        imported.load(s.export())
        self.assertEqual(imported.world.digest(), s.world.digest())

    def test_local_model_learns_only_observed_transition(self):
        model = LocalTransitionModel()
        model.fit_pair([["火", "木"]], [["火", "炭"]])
        self.assertEqual(model.predict([["火", "木"]]), [["火", "炭"]])
        self.assertEqual(model.predict([["水"]]), [["水"]])


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.app = Workbench().start()
        self.url = f"http://127.0.0.1:{self.app.port}"

    def tearDown(self):
        self.app.close()

    def request(self, path, payload=None, token=True, origin=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-SWM-Token"] = self.app.token
        if origin:
            headers["Origin"] = origin
        req = Request(self.url + path, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
        return urlopen(req, timeout=5)

    def test_web_actions_export_and_reimport(self):
        with self.request("/api/step", {"count": 3}) as response:
            self.assertEqual(json.load(response)["world"]["tick"], 3)
        with self.request("/api/export") as response:
            replay = json.load(response)
        with self.request("/api/import", replay) as response:
            self.assertEqual(json.load(response)["world"]["tick"], 3)

    def test_api_rejects_missing_capability_and_foreign_origin(self):
        for kwargs in ({"token": False}, {"origin": "https://example.org"}):
            with self.assertRaises(HTTPError) as caught:
                self.request("/api/step", {"count": 1}, **kwargs)
            self.assertEqual(caught.exception.code, 403)
        self.assertEqual(self.app.session.world.tick, 0)

    def test_bad_request_returns_error_without_mutation(self):
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/action", {"kind": "water", "x": -1, "y": 0})
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(self.app.session.cursor, 0)


if __name__ == "__main__":
    unittest.main()
