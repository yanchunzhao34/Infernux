"""An honest observation-only learned baseline, usable without a GPU.

Learns local symbol transitions from trajectories. The simulator remains the
teacher. This is not claimed to discover physical causes or semantic objects.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import random

from .scenarios import create


def features(grid, x, y):
    h, w = len(grid), len(grid[0])
    def at(px, py):
        return grid[py][px] if 0 <= px < w and 0 <= py < h else "#"
    return tuple(at(x + dx, y + dy) for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)))


class LocalTransitionModel:
    def __init__(self):
        self.counts = defaultdict(Counter)

    def fit_pair(self, before, after):
        for y, row in enumerate(before):
            for x, symbol in enumerate(row):
                if symbol != "，" and after[y][x] != "，":
                    self.counts[features(before, x, y)][after[y][x]] += 1

    def predict(self, grid):
        return [[self.counts[key].most_common(1)[0][0] if key in self.counts else symbol
                 for x, symbol in enumerate(row) for key in [features(grid, x, y)]]
                for y, row in enumerate(grid)]

    def document(self):
        return {"schema": "infernux.swm.local-transition/1", "input": "five-glyph-neighborhood",
                "counts": [{"context": list(k), "next": dict(v)} for k, v in sorted(self.counts.items())]}


def experiment(training_worlds=6, steps=80):
    model = LocalTransitionModel()
    for seed in range(training_worlds):
        w = create("fire", seed)
        rng = random.Random(seed)
        # Translate the experiments to avoid sharing absolute positions.
        for f in ("ground", "fuel", "moisture", "oxygen", "temperature"):
            import numpy as np
            setattr(w, f, np.roll(getattr(w, f), seed % 5, axis=0))
        w.temperature[w.fuel > 0] += rng.uniform(0, 80)
        for _ in range(steps):
            before = w.glyphs()
            w.step()
            model.fit_pair(before, w.glyphs())
    w = create("fire", 1001)
    w.moisture[w.fuel > 0] *= 0.8
    w.temperature[w.fuel > 0] += 45
    correct = persistence = total = changed = changed_correct = 0
    for _ in range(steps):
        before = w.glyphs()
        predicted = model.predict(before)
        w.step()
        after = w.glyphs()
        for y, row in enumerate(after):
            for x, value in enumerate(row):
                total += 1
                correct += predicted[y][x] == value
                persistence += before[y][x] == value
                if before[y][x] != value:
                    changed += 1
                    changed_correct += predicted[y][x] == value
    return model, {"training_worlds": training_worlds, "evaluation": "held-out material condition",
                   "accuracy": correct / total, "persistence_accuracy": persistence / total,
                   "changed_cells": changed, "changed_cell_accuracy": changed_correct / changed if changed else None,
                   "limitations": "Observation-only local baseline; no claim of causal or object discovery."}
