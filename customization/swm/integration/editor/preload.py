from infernux.lifecycle import InxPreload


class SWMEditorPreload(InxPreload):
    def preload(self, context):
        from . import service
        from . import panel  # registration is owned by this preload
        service.start()
        context.add_cleanup(service.stop)

    def unload(self):
        pass
