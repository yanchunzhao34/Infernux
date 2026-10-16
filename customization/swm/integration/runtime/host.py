"""Attach SWMHost to a scene object to advance the world during Play."""
from infernux.components import InxComponent, serialized_field
from . import state
from .swm_core.world import DT


class SWMHost(InxComponent):
    auto_step: bool = serialized_field(default=False)

    def awake(self):
        self._elapsed = 0.0

    def fixed_update(self, fixed_delta_time):
        if not self.auto_step:
            return
        self._elapsed = getattr(self, "_elapsed", 0.0) + fixed_delta_time
        with state.lock:
            while self._elapsed + 1e-9 >= DT:
                state.session.step()
                self._elapsed -= DT

    def observe(self):
        with state.lock:
            return state.session.world.observation()

    def act(self, command):
        with state.lock:
            state.session.action(command)
