"""Editor-independent session, bounded history, and verifiable replay."""
from __future__ import annotations

import copy

from .scenarios import SCENARIOS, create
from .world import World, VERSION


class Session:
    def __init__(self, scenario="garden"):
        self.world = create(scenario)
        self.initial = self.world.snapshot()
        self.operations = []
        self.frames = [(0, self.world.snapshot())]
        self.cursor = 0

    def reset(self, scenario):
        replacement = Session(scenario)
        self.__dict__.update(replacement.__dict__)

    def _record(self, op):
        # Editing at an earlier checkpoint deliberately creates a new branch.
        self.operations = self.operations[:self.cursor]
        self.frames = [(i, s) for i, s in self.frames if i <= self.cursor]
        self.operations.append(copy.deepcopy(op))
        self.cursor += 1
        self.frames.append((self.cursor, self.world.snapshot()))
        self.frames = self.frames[-241:]

    def action(self, command):
        self.world.apply(command)
        self._record({"action": command})

    def step(self, count=1):
        self.world.step(count)
        self._record({"step": count})

    def seek(self, index):
        if type(index) is not int:
            raise ValueError("回放位置必须是整数")
        frame = next((s for i, s in self.frames if i == index), None)
        if frame is None:
            raise ValueError("此检查点已不在最近 240 次操作窗口中")
        self.world = World.restore(frame)
        self.cursor = index

    def export(self):
        return {"schema": "infernux.swm.replay/1", "version": VERSION,
                "initial": copy.deepcopy(self.initial),
                "operations": copy.deepcopy(self.operations[:self.cursor]),
                "final_hash": self.world.digest()}

    def load(self, document):
        if not isinstance(document, dict) or document.get("schema") != "infernux.swm.replay/1" or document.get("version") != VERSION:
            raise ValueError("请导入本版本导出的 SWM 回放文件")
        ops = document.get("operations")
        if not isinstance(ops, list) or len(ops) > 20000:
            raise ValueError("回放最多支持 20000 次操作")
        # Full verification is transactional. An invalid import keeps this session.
        candidate = Session("blank")
        candidate.world = World.restore(document["initial"])
        candidate.initial = candidate.world.snapshot()
        candidate.frames = [(0, candidate.world.snapshot())]
        for op in ops:
            if not isinstance(op, dict) or len(op) != 1:
                raise ValueError("回放操作格式非法")
            if "step" in op:
                if type(op["step"]) is not int or not 1 <= op["step"] <= 100:
                    raise ValueError("回放步数非法")
                candidate.step(op["step"])
            elif "action" in op:
                candidate.action(op["action"])
            else:
                raise ValueError("未知回放操作")
        if candidate.world.digest() != document.get("final_hash"):
            raise ValueError("回放校验失败：最终状态与原记录不一致")
        self.__dict__.update(candidate.__dict__)

    def view(self):
        return {"version": VERSION, "world": self.world.snapshot(),
                "observation": self.world.observation(), "stats": self.world.stats(),
                "rooms": self.world.rooms(), "scenarios": SCENARIOS,
                "history": {"first": self.frames[0][0], "last": self.frames[-1][0], "cursor": self.cursor}}
