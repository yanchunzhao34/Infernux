"""Stage one source of truth into an InxPackage and a standalone source ZIP."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def copy_sources(source, destination, *, exclude=()):
    for path in sorted(source.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc" or path.name in exclude:
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def stage(stage_root):
    package = stage_root / "package"
    # Unique staging directories prevent stale files without recursive deletion.
    if package.exists():
        raise ValueError("请选择新的暂存目录，避免把旧文件混入插件")
    runtime = package / "runtime" / "swm_runtime"
    editor = package / "editor" / "swm_editor"
    copy_sources(ROOT / "swm_core", runtime / "swm_core", exclude=("learning.py",))
    copy_sources(ROOT / "integration" / "runtime", runtime)
    copy_sources(ROOT / "integration" / "editor", editor)
    copy_sources(ROOT / "swm_workbench", editor / "swm_workbench", exclude=("__main__.py",))
    # InxPackage owns a private module namespace. Cross-role imports are rooted
    # at its unique runtime package; package-local modules use relative imports.
    for file in (editor / "swm_workbench").glob("*.py"):
        source = file.read_text(encoding="utf-8")
        file.write_text(source.replace("from swm_core", "from swm_runtime.swm_core"), encoding="utf-8")
    (package / "inx_package.json").write_text(json.dumps({
        "reference": "yanchunzhao34/swm", "name": "语义世界 SWM", "version": "0.1.0",
        "engine": ">=0.4.2,<0.5", "intro": "汉字世界、隐藏状态、过程演化、守恒水流与可验证回放。"
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    pages = package / "plugin_pages"
    pages.mkdir(parents=True)
    shutil.copyfile(ROOT / "README.md", pages / "usage.zh-CN.md")
    for document in ("ARCHITECTURE.md", "VERIFICATION.md"):
        shutil.copyfile(ROOT / document, pages / document)
    shutil.copyfile(REPO / "LICENSE", package / "LICENSE.txt")
    return package


def build(stage_root, destination):
    package = stage(stage_root)
    spec = importlib.util.spec_from_file_location("swm_inxpack", ROOT / "tools" / "inxpack.py")
    packer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packer)
    packer.PACKAGE_ROOT = package
    destination.mkdir(parents=True, exist_ok=True)
    artifact = destination / "infernux-swm-0.1.0.inxpkg"
    packer.build(artifact)
    metadata = packer.verify(artifact)
    with zipfile.ZipFile(destination / "infernux-swm-0.1.0-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, "infernux-swm/" + path.relative_to(ROOT).as_posix())
        archive.write(REPO / "LICENSE", "infernux-swm/LICENSE")
    return artifact, metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=REPO / "dist" / "releases" / "swm-0.1.0")
    args = parser.parse_args()
    build(args.stage.resolve(), args.output.resolve())
