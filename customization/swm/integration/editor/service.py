from swm_runtime import state
from .swm_workbench.server import Workbench

app = None


def start():
    global app
    if app is None:
        app = Workbench(session=state.session, lock=state.lock).start()
    return app


def stop():
    global app
    if app is not None:
        app.close()
        app = None
