"""A small, explicit world: symbols observe persistent numeric state.

This is an educational reference simulator, not a chemistry or CFD solver.
Water transport conserves volume. Material accounting conserves a fuel-derived
tracer (fuel + char + ash + released gas), not total chemical mass including air.
All transport reads an old-state snapshot; pair fluxes are limited together.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import deque

import numpy as np

VERSION = "0.1.0"
SCHEMA = "infernux.swm.world/1"
DT = 0.1
GLYPHS = ["土", "墙", "门", "石", "草", "木", "床", "叶"]
FIELDS = ("ground", "elevation", "water", "temperature", "fuel", "char",
          "ash", "gas", "moisture", "oxygen", "door_open", "observed")
FLOAT_FIELDS = FIELDS[1:10]
VOCABULARY = ["土", "墙", "门", "石", "草", "木", "床", "叶", "水", "火", "炭", "灰", "人", "，"]


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必须为数值")
    value = float(value)
    if not np.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} 必须在 {low} 到 {high} 之间")
    return value


class World:
    def __init__(self, width=32, height=24, seed=7):
        if type(width) is not int or type(height) is not int or not (4 <= width <= 64 and 4 <= height <= 64):
            raise ValueError("地图宽高必须是 4–64 的整数")
        self.width, self.height = width, height
        self.seed, self.tick, self.revision = int(seed), 0, 0
        self.name = "空白世界"
        shape = (height, width)
        self.ground = np.zeros(shape, dtype=np.int16)
        for field in FLOAT_FIELDS:
            setattr(self, field, np.zeros(shape, dtype=np.float64))
        self.temperature.fill(20.0)
        self.oxygen.fill(1.0)
        self.door_open = np.zeros(shape, dtype=bool)
        self.observed = np.ones(shape, dtype=bool)
        self.actor = [2, 2]
        self.events = []
        self.water_in = self.water_out = 0.0
        self.material_in = self.material_out = 0.0
        self.initial_water = self.initial_material = 0.0

    def baseline(self):
        self.initial_water = float(self.water.sum())
        self.initial_material = self.material_total()
        self.water_in = self.water_out = self.material_in = self.material_out = 0.0

    def material_total(self):
        return float(sum(getattr(self, f).sum() for f in ("fuel", "char", "ash", "gas")))

    def event(self, kind, x, y, detail):
        self.events.append({"tick": self.tick, "kind": kind, "x": x, "y": y, "detail": detail})
        self.events = self.events[-160:]

    def blocked(self):
        return (self.ground == 1) | (self.ground == 3) | ((self.ground == 2) & ~self.door_open)

    def _cell(self, command):
        x, y = command.get("x"), command.get("y")
        if type(x) is not int or type(y) is not int or not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError("格点坐标超出地图")
        return x, y

    def apply(self, command):
        """Validate on a private candidate: invalid commands cannot partially edit."""
        if not isinstance(command, dict):
            raise ValueError("动作必须是对象")
        candidate = copy.deepcopy(self)
        candidate._apply(command)
        candidate.validate()
        candidate.revision += 1
        self.__dict__.update(candidate.__dict__)

    def _apply(self, c):
        kind = c.get("kind")
        if kind == "move":
            dx, dy = c.get("dx"), c.get("dy")
            if type(dx) is not int or type(dy) is not int or abs(dx) + abs(dy) != 1:
                raise ValueError("每次只能向相邻格移动一步")
            x, y = self.actor[0] + dx, self.actor[1] + dy
            if 0 <= x < self.width and 0 <= y < self.height and not self.blocked()[y, x] and self.water[y, x] <= 1.5:
                self.actor = [x, y]
                self.event("移动", x, y, "进入可通行邻格")
            else:
                self.event("阻挡", *self.actor, "墙、闭门、石或深水阻挡移动")
            return
        x, y = self._cell(c)
        if kind == "paint":
            glyph = c.get("glyph")
            if glyph not in VOCABULARY:
                raise ValueError("未知的汉字笔刷")
            if glyph == "人":
                if self.blocked()[y, x] or self.water[y, x] > 1.5:
                    raise ValueError("人需要放在可通行格")
                self.actor = [x, y]
            elif glyph == "，":
                self.observed[y, x] = False
            elif glyph == "水":
                self._add_water(x, y, 0.5)
            elif glyph == "火":
                if self.fuel[y, x] + self.char[y, x] <= 0:
                    raise ValueError("先放置木、草或叶，再点火")
                self.temperature[y, x] = 600.0
                self.observed[y, x] = True
            elif glyph in ("炭", "灰"):
                self._clear_material(x, y)
                self.ground[y, x] = 0
                getattr(self, "char" if glyph == "炭" else "ash")[y, x] = 1.0
                self.material_in += 1.0
                self.observed[y, x] = True
            else:
                index = GLYPHS.index(glyph)
                if [x, y] == self.actor and index in (1, 2, 3):
                    raise ValueError("请先移动此处的人")
                self._clear_material(x, y)
                self.ground[y, x], self.door_open[y, x] = index, False
                amount = {4: 0.6, 5: 1.5, 7: 0.3}.get(index, 0.0)
                self.fuel[y, x] = amount
                self.material_in += amount
                self.moisture[y, x] = 0.05 if amount else 0
                self.temperature[y, x] = 20
                self.observed[y, x] = True
                if index in (1, 2, 3):
                    self.water_out += float(self.water[y, x])
                    self.water[y, x] = 0
            self.event("编辑", x, y, f"笔刷：{glyph}")
        elif kind == "water":
            amount = number(c.get("amount", 0.5), "注水量", 0, 100)
            self._add_water(x, y, amount)
            self.event("注水", x, y, f"外部注入 {amount:g} 单位水")
        elif kind == "door":
            if self.ground[y, x] != 2:
                raise ValueError("选中一个门格")
            if self.door_open[y, x] and [x, y] == self.actor:
                raise ValueError("人还在门中，不能关门")
            if self.door_open[y, x] and self.water[y, x] > 0:
                raise ValueError("门格有水，请先移出水量再关门")
            self.door_open[y, x] = not self.door_open[y, x]
            self.event("门", x, y, "打开" if self.door_open[y, x] else "关闭")
        elif kind == "set":
            allowed = {"elevation": (-5, 10), "temperature": (0, 1500), "moisture": (0, 1), "oxygen": (0, 1)}
            field = c.get("field")
            if field not in allowed:
                raise ValueError("此属性不可直接修改")
            value = number(c.get("value"), field, *allowed[field])
            getattr(self, field)[y, x] = value
            self.event("属性", x, y, f"{field} = {value:g}")
        elif kind == "reveal":
            self.observed[y, x] = True
        else:
            raise ValueError("未知动作")

    def _clear_material(self, x, y):
        for field in ("fuel", "char", "ash", "gas"):
            self.material_out += float(getattr(self, field)[y, x])
            getattr(self, field)[y, x] = 0

    def _add_water(self, x, y, amount):
        if self.blocked()[y, x]:
            raise ValueError("障碍格不能注水")
        self.water[y, x] += amount
        self.water_in += amount

    def step(self, count=1):
        if type(count) is not int or not 1 <= count <= 100:
            raise ValueError("步数必须是 1–100 的整数")
        candidate = copy.deepcopy(self)
        for _ in range(count):
            candidate._step()
            candidate.validate()
        candidate.revision += count
        self.__dict__.update(candidate.__dict__)

    def _step(self):
        self.tick += 1
        blocked = self.blocked()
        heads = self.elevation + self.water
        # Two directed arrays cover each undirected edge exactly once.
        right = (heads[:, :-1] - heads[:, 1:]) * 0.12
        down = (heads[:-1, :] - heads[1:, :]) * 0.12
        right[blocked[:, :-1] | blocked[:, 1:]] = 0
        down[blocked[:-1, :] | blocked[1:, :]] = 0
        out = np.zeros_like(self.water)
        out[:, :-1] += np.maximum(right, 0)
        out[:, 1:] += np.maximum(-right, 0)
        out[:-1, :] += np.maximum(down, 0)
        out[1:, :] += np.maximum(-down, 0)
        scale = np.minimum(1.0, self.water / np.maximum(out, 1e-30))
        right *= np.where(right >= 0, scale[:, :-1], scale[:, 1:])
        down *= np.where(down >= 0, scale[:-1, :], scale[1:, :])
        delta = np.zeros_like(self.water)
        delta[:, :-1] -= right
        delta[:, 1:] += right
        delta[:-1, :] -= down
        delta[1:, :] += down
        self.water += delta
        # Roundoff only; the donor limiter enforces nonnegative amounts.
        self.water[np.abs(self.water) < 1e-14] = 0

        old = self.temperature.copy()
        heat = np.zeros_like(old)
        h = (old[:, :-1] - old[:, 1:]) * 0.035
        v = (old[:-1, :] - old[1:, :]) * 0.035
        h[blocked[:, :-1] | blocked[:, 1:]] = 0
        v[blocked[:-1, :] | blocked[1:, :]] = 0
        heat[:, :-1] -= h
        heat[:, 1:] += h
        heat[:-1, :] -= v
        heat[1:, :] += v
        self.temperature += heat
        self.temperature += (20 - self.temperature) * (0.008 + np.minimum(self.water, 1) * 0.18)

        burning = (self.temperature > 160) & (self.fuel + self.char > 1e-8)
        dryness = 1 - 0.95 * self.moisture
        activity = np.maximum(self.temperature - 160, 0) / 440
        consumed = np.minimum(self.fuel, 0.045 * activity * dryness)
        oxidation = consumed * self.oxygen
        pyrolysis = consumed - oxidation
        self.fuel -= consumed
        self.char += pyrolysis * 0.4
        self.ash += oxidation * 0.05
        self.gas += oxidation * 0.95 + pyrolysis * 0.6
        char_used = np.minimum(self.char, 0.008 * activity * self.oxygen * dryness)
        self.char -= char_used
        self.ash += char_used * 0.05
        self.gas += char_used * 0.95
        self.temperature += oxidation * 1400 + char_used * 800
        self.temperature = np.minimum(self.temperature, 1500)
        # Moisture and oxygen are controlled experimental parameters in v0.1.
        # They are not claimed to be a conserved fluid/chemical model.
        if np.any(burning) and (self.tick == 1 or self.tick % 10 == 0):
            y, x = np.argwhere(burning)[0]
            self.event("材料过程", int(x), int(y),
                       f"传热 → 条件检查 → 氧化/热解；本步消耗 {consumed.sum():.4f} 燃料")
        if self.tick % 20 == 0 and np.abs(right).sum() + np.abs(down).sum() > 1e-8:
            self.event("水流", 0, 0, "按水面高度差交换；总出流受可用水量限制")

    def validate(self):
        shape = (self.height, self.width)
        for field in FIELDS:
            a = getattr(self, field)
            if a.shape != shape or not np.isfinite(a).all():
                raise ValueError(f"{field} 形状或数值非法")
        if (self.ground < 0).any() or (self.ground >= len(GLYPHS)).any():
            raise ValueError("材料类型非法")
        for field in ("water", "fuel", "char", "ash", "gas"):
            if (getattr(self, field) < -1e-10).any():
                raise ValueError(f"{field} 出现负值")
        for field in ("moisture", "oxygen"):
            if ((getattr(self, field) < 0) | (getattr(self, field) > 1)).any():
                raise ValueError(f"{field} 超出 0–1")
        if (self.temperature < 0).any() or (self.temperature > 1500).any():
            raise ValueError("温度超出支持范围")
        if ((self.elevation < -5) | (self.elevation > 10)).any():
            raise ValueError("高程超出支持范围")
        if np.any(self.water[self.blocked()] > 1e-10):
            raise ValueError("障碍内存在水")
        if not isinstance(self.actor, list) or len(self.actor) != 2 or any(type(v) is not int for v in self.actor):
            raise ValueError("角色位置非法")
        x, y = self.actor
        if not (0 <= x < self.width and 0 <= y < self.height) or self.blocked()[y, x]:
            raise ValueError("角色位置不可通行")
        if abs(self.water.sum() - self.initial_water - self.water_in + self.water_out) > 1e-7:
            raise ValueError("水量收支不平衡")
        if abs(self.material_total() - self.initial_material - self.material_in + self.material_out) > 1e-7:
            raise ValueError("燃料来源物质收支不平衡")

    def glyphs(self):
        result = np.array(GLYPHS)[self.ground].copy()
        material = np.isin(self.ground, [4, 5, 7])
        result[material & (self.fuel < 1e-6)] = "土"
        result[self.ash > 0.01] = "灰"
        result[self.char > 0.01] = "炭"
        result[(self.fuel + self.char > 1e-6) & (self.temperature > 160)] = "火"
        result[self.water > 0.05] = "水"
        result[self.actor[1], self.actor[0]] = "人"
        result[~self.observed] = "，"
        return result.tolist()

    def observation(self):
        """Public model input excludes hidden fields and internal event labels."""
        return {"tick": self.tick, "glyphs": self.glyphs(), "visible": self.observed.tolist(),
                "width": self.width, "height": self.height, "view": "top-down+elevation"}

    def rooms(self):
        """Reference geometry only: not a learned concept or a model input."""
        seen = np.zeros((self.height, self.width), dtype=bool)
        blocked = self.blocked()
        rooms = []
        for y in range(self.height):
            for x in range(self.width):
                if seen[y, x] or blocked[y, x]:
                    continue
                queue, cells, boundary = deque([(x, y)]), [], False
                seen[y, x] = True
                while queue:
                    cx, cy = queue.popleft()
                    cells.append([cx, cy])
                    boundary |= cx in (0, self.width - 1) or cy in (0, self.height - 1)
                    for nx, ny in ((cx-1, cy), (cx+1, cy), (cx, cy-1), (cx, cy+1)):
                        if 0 <= nx < self.width and 0 <= ny < self.height and not seen[ny, nx] and not blocked[ny, nx]:
                            seen[ny, nx] = True
                            queue.append((nx, ny))
                if not boundary:
                    rooms.append({"area": len(cells), "cells": cells, "source": "reference-geometry"})
        return rooms

    def inspect(self, x, y):
        self._cell({"x": x, "y": y})
        return {"x": x, "y": y, "glyph": self.glyphs()[y][x],
                "material": GLYPHS[int(self.ground[y, x])],
                **{f: float(getattr(self, f)[y, x]) for f in FLOAT_FIELDS},
                "door_open": bool(self.door_open[y, x]), "observed": bool(self.observed[y, x])}

    def stats(self):
        return {"water": float(self.water.sum()), "water_error": float(self.water.sum() - self.initial_water - self.water_in + self.water_out),
                "material": self.material_total(), "material_error": self.material_total() - self.initial_material - self.material_in + self.material_out,
                "fuel": float(self.fuel.sum()), "char": float(self.char.sum()), "ash": float(self.ash.sum()), "gas": float(self.gas.sum()),
                "max_temperature": float(self.temperature.max())}

    def snapshot(self):
        return {"schema": SCHEMA, "version": VERSION, "dt": DT,
                "width": self.width, "height": self.height, "seed": self.seed,
                "tick": self.tick, "revision": self.revision, "name": self.name,
                "actor": list(self.actor), "events": copy.deepcopy(self.events),
                "accounting": {k: getattr(self, k) for k in ("water_in", "water_out", "material_in", "material_out", "initial_water", "initial_material")},
                "fields": {f: getattr(self, f).tolist() for f in FIELDS}}

    @classmethod
    def restore(cls, data):
        if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("version") != VERSION or data.get("dt") != DT:
            raise ValueError("世界格式或运行规则版本不匹配")
        w = cls(data.get("width"), data.get("height"), data.get("seed", 7))
        for field in FIELDS:
            values = np.asarray(data["fields"][field])
            if field == "ground" and (not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all()
                                      or not ((values >= 0) & (values < len(GLYPHS))).all()):
                raise ValueError("材料 ID 必须为有效整数")
            if field in ("observed", "door_open") and not np.isin(values, [0, 1]).all():
                raise ValueError("掩码必须是布尔值")
            setattr(w, field, np.array(values, dtype=getattr(w, field).dtype))
        for field in ("tick", "revision"):
            if type(data[field]) is not int or data[field] < 0:
                raise ValueError("时间/版本非法")
            setattr(w, field, data[field])
        w.name = str(data.get("name", "导入世界"))[:80]
        w.actor = copy.deepcopy(data["actor"])
        for key in w.snapshot()["accounting"]:
            setattr(w, key, number(data["accounting"][key], key, 0, 1e9))
        # Imported event text is diagnostic data, never executable instructions.
        events = data.get("events", [])
        if not isinstance(events, list) or len(events) > 160:
            raise ValueError("事件列表非法")
        for event in events:
            if (not isinstance(event, dict)
                    or type(event.get("tick")) is not int or not 0 <= event["tick"] <= w.tick
                    or not isinstance(event.get("kind"), str) or len(event["kind"]) > 80
                    or not isinstance(event.get("detail"), str) or len(event["detail"]) > 1000):
                raise ValueError("事件内容非法")
            w._cell(event)
        w.events = copy.deepcopy(events)
        w.validate()
        return w

    def digest(self):
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":"), allow_nan=False).encode()).hexdigest()
