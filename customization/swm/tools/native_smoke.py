"""Exercise the actual installed native package (no engine stubs)."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    project.mkdir(parents=True, exist_ok=True)
    os.environ["INFERNUX_PACKAGE_CACHE_ROOT"] = str(project / "Cache" / "Packages")
    from infernux.plugins import PluginManager, InxPackage
    from infernux.engine.project_context import set_project_root
    from infernux.version import ENGINE_RELEASE

    for name in ("Assets", "ProjectSettings"):
        (project / name).mkdir(exist_ok=True)
    (project / ".infernux-version").write_text(ENGINE_RELEASE + "\n", encoding="utf-8")
    requirements = project / "ProjectSettings" / "requirements.txt"
    if not requirements.exists():
        requirements.write_text("numpy>=1.26\n", encoding="utf-8")
    set_project_root(str(project))
    preview = InxPackage.inspect(str(args.package.resolve()))
    assert preview.metadata["reference"] == "yanchunzhao34/swm"
    manager = PluginManager(str(project))
    try:
        result = manager.install_package(str(args.package.resolve()), install_dependencies=False)
        if not result.loaded or result.error:
            raise RuntimeError(json.dumps(result.snapshot(), ensure_ascii=False))
        modules = [m for n, m in list(sys.modules.items()) if n.endswith("swm_editor.service")]
        assert len(modules) == 1, [getattr(m, "__name__", None) for m in modules]
        service = modules[0]
        app = service.app
        assert app is not None and app.thread.is_alive()
        runtime = service.state
        assert app.session is runtime.session
        host_module = importlib.import_module(runtime.__package__ + ".host")
        host = host_module.SWMHost()
        host.auto_step = True
        host.awake()
        for _ in range(5):
            host.fixed_update(0.02)
        assert host.observe()["tick"] == 1
        host.act({"kind": "water", "x": 22, "y": 16, "amount": 0.5})
        assert abs(runtime.session.world.stats()["water"] - 28.5) < 1e-9
        print(json.dumps({"engine": ENGINE_RELEASE, "package_loaded": True,
                          "shared_session": True, "host_ticks": 1,
                          "plugin_preloads": result.snapshot()["preload_instances"]}, ensure_ascii=False))
    finally:
        manager.shutdown()
    assert service.app is None
    print("Plugin service cleanup: PASS")


if __name__ == "__main__":
    main()
