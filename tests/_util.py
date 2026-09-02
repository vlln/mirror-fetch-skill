"""测试共享工具：加载引擎模块 + 本地 HTTP server（离线 e2e 用）。"""
import importlib.util
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ENGINE = (Path(__file__).parents[1] / "skills" / "mirror-fetch" / "scripts" / "mirror-fetch").resolve()
assert ENGINE.is_file(), ENGINE

import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402

# 引擎文件无 .py 后缀 → 必须显式 SourceFileLoader
_loader = importlib.machinery.SourceFileLoader("mirror_fetch_engine", str(ENGINE))
_spec = importlib.util.spec_from_loader("mirror_fetch_engine", _loader)
mf = importlib.util.module_from_spec(_spec)
_loader.exec_module(mf)


class _QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 静音访问日志
        pass


def make_handler(body: bytes, routes=None):
    """按 path 返回 (code, body)；默认 200 + body。routes: {path: (code, body)}。"""
    routes = routes or {}

    class H(_QuietHandler):
        def do_GET(self):  # noqa: N802
            code, payload = routes.get(self.path, (200, body))
            self.send_response(code)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except BrokenPipeError:
                pass

        def do_HEAD(self):  # noqa: N802
            code, payload = routes.get(self.path, (200, body))
            self.send_response(code)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()

    return H


class LocalServer:
    """起一个本地 HTTP server；host 形如 '127.0.0.1:PORT'（engine 的 netloc 含端口）。"""

    def __init__(self, handler_cls):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        self.host = f"127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
