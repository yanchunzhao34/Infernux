import webbrowser

from infernux.engine.interaction import PanelInteractionDescriptor
from infernux.engine.ui.editor_panel import EditorPanel
from infernux.engine.ui.panel_registry import editor_panel
from swm_runtime import state
from . import service


@editor_panel("语义世界 SWM", type_id="swm.workbench", menu_path="Extensions/SWM",
              interaction=PanelInteractionDescriptor())
class SWMPanel(EditorPanel):
    def __init__(self):
        super().__init__("语义世界 SWM", "swm.workbench")

    def _initial_size(self):
        return 650.0, 720.0

    def on_render_content(self, ctx):
        ctx.label("Infernux-SWM 0.1 · 汉字语义世界")
        ctx.text_wrapped("点击打开完整工作台，绘制汉字、注水、改变材料条件并检查过程。")
        if ctx.button("打开语义世界工作台"):
            webbrowser.open(service.start().url)
        ctx.same_line()
        if ctx.button("单步演化"):
            with state.lock:
                state.session.step()
        ctx.separator()
        with state.lock:
            world = state.session.world
            ctx.label(f"{world.name} / tick {world.tick} / 水量 {world.water.sum():.3f}")
            ctx.text_wrapped("SWMHost.auto_step 默认关闭。启用后可由场景固定步驱动；此时请暂停浏览器自动播放。")
            for row in world.glyphs():
                ctx.label(" ".join(row))
            ctx.separator()
            for event in world.events[-3:]:
                ctx.text_wrapped(f"[{event['tick']}] {event['kind']}: {event['detail']}")
