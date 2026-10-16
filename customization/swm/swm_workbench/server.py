"""Loopback-only workbench; all mutation requests require a session capability."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit

from swm_core.session import Session

STATIC = Path(__file__).with_name("static")


class Workbench:
    def __init__(self, port=0, scenario="garden", *, session=None, lock=None):
        self.session = session if session is not None else Session(scenario)
        self.token = secrets.token_urlsafe(24)
        self.lock = lock if lock is not None else threading.RLock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def send(self, data, status=200, mime="application/json; charset=utf-8"):
                raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(raw)

            def valid_host(self):
                return self.headers.get("Host") in (f"127.0.0.1:{owner.port}", f"localhost:{owner.port}")

            def do_GET(self):
                if not self.valid_host():
                    return self.send({"error": "Invalid host"}, 403)
                path = urlsplit(self.path).path
                if path in ("/api/state", "/api/export"):
                    if self.headers.get("X-SWM-Token") != owner.token:
                        return self.send({"error": "会话已失效，请重新打开工作台"}, 403)
                    with owner.lock:
                        return self.send(owner.session.view() if path == "/api/state" else owner.session.export())
                files = {"/": ("index.html", "text/html; charset=utf-8"),
                         "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                         "/style.css": ("style.css", "text/css; charset=utf-8")}
                if path not in files:
                    return self.send({"error": "Not found"}, 404)
                filename, mime = files[path]
                self.send((STATIC / filename).read_bytes(), mime=mime)

            def do_POST(self):
                if not self.valid_host() or self.headers.get("X-SWM-Token") != owner.token:
                    return self.send({"error": "会话验证失败"}, 403)
                origin = self.headers.get("Origin")
                if origin and origin not in (f"http://127.0.0.1:{owner.port}", f"http://localhost:{owner.port}"):
                    return self.send({"error": "跨来源请求被拒绝"}, 403)
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    return self.send({"error": "需要 JSON 请求"}, 415)
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 8_000_000:
                        return self.send({"error": "文件太大或内容为空"}, 413)
                    data = json.loads(self.rfile.read(size))
                    if not isinstance(data, dict):
                        raise ValueError("请求必须是对象")
                    path = urlsplit(self.path).path
                    with owner.lock:
                        if path == "/api/action":
                            owner.session.action(data)
                        elif path == "/api/step":
                            owner.session.step(data.get("count", 1))
                        elif path == "/api/reset":
                            owner.session.reset(data.get("scenario", "garden"))
                        elif path == "/api/seek":
                            owner.session.seek(data.get("index"))
                        elif path == "/api/import":
                            owner.session.load(data)
                        else:
                            return self.send({"error": "未知接口"}, 404)
                        self.send(owner.session.view())
                except (ValueError, TypeError, KeyError, OverflowError) as error:
                    self.send({"error": str(error)}, 400)

        self.http = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.http.daemon_threads = True
        self.port = self.http.server_address[1]
        self.thread = None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/#{self.token}"

    def start(self):
        self.thread = threading.Thread(target=self.http.serve_forever, name="swm-workbench", daemon=True)
        self.thread.start()
        return self

    def close(self):
        if self.thread:
            self.http.shutdown()
            self.thread.join(timeout=5)
            self.thread = None
        self.http.server_close()
