"""Four inspectable experiments, all in the same top-down coordinate frame."""
from .world import World

SCENARIOS = {"garden": "院落与湖泊", "water": "湖泊注水", "fire": "湿木与供氧", "room": "门与房间", "blank": "空白画布"}


def create(name="garden", seed=7):
    if name not in SCENARIOS:
        raise ValueError("未知场景")
    w = World(seed=seed)
    w.name = SCENARIOS[name]
    w.actor = [3, 4]
    if name in ("garden", "room"):
        w.ground[2, 2:12] = w.ground[11, 2:12] = 1
        w.ground[2:12, 2] = w.ground[2:12, 11] = 1
        w.ground[7, 11] = 2
        w.ground[4:6, 5:7] = 6
    if name in ("garden", "water"):
        w.elevation.fill(0.8)
        w.elevation[12:21, 17:29] = -0.5
        w.elevation[14:19, 19:27] = -1
        w.water[14:19, 19:27] = 0.7
        w.ground[12:21, 16] = 4
        w.fuel[12:21, 16] = 0.6
        w.moisture[12:21, 16] = 0.1
    if name == "garden":
        for x, y in [(19, 5), (24, 6), (27, 3)]:
            w.ground[y-1:y+2, x-1:x+2] = 7
            w.fuel[y-1:y+2, x-1:x+2] = 0.3
            w.ground[y, x] = 5
            w.fuel[y, x] = 1.5
        w.ground[15:18, 4:10] = 4
        w.fuel[15:18, 4:10] = 0.6
        w.ground[16, 6] = 5
        w.fuel[16, 6] = 1.5
    if name == "fire":
        for x, moisture, oxygen in [(6, 0.05, 1), (15, 0.85, 1), (24, 0.05, 0.05)]:
            w.ground[8:12, x:x+2] = 5
            w.fuel[8:12, x:x+2] = 1.5
            w.moisture[8:12, x:x+2] = moisture
            w.oxygen[8:12, x:x+2] = oxygen
            w.temperature[8:12, x:x+2] = 460
    w.baseline()
    w.validate()
    return w
