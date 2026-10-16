from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import webbrowser


def main():
    parser = argparse.ArgumentParser(description="Infernux-SWM 汉字语义世界工作台")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--connection-file", type=Path)
    parser.add_argument("--train", type=Path, help="训练局部符号基线，并将模型和指标保存到目录")
    args = parser.parse_args()
    if args.train:
        from swm_core.learning import experiment
        model, metrics = experiment()
        args.train.mkdir(parents=True, exist_ok=True)
        (args.train / "model.json").write_text(json.dumps(model.document(), ensure_ascii=False, indent=2), encoding="utf-8")
        (args.train / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(metrics, ensure_ascii=False))
        return
    from .server import Workbench
    app = Workbench(args.port).start()
    if args.connection_file:
        args.connection_file.parent.mkdir(parents=True, exist_ok=True)
        args.connection_file.write_text(json.dumps({"url": app.url, "port": app.port}), encoding="utf-8")
    print(f"Infernux-SWM: {app.url}", flush=True)
    if not args.no_browser:
        webbrowser.open(app.url)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()


if __name__ == "__main__":
    main()
