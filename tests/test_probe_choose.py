"""probe 分类（离线本地 server 返回各状态码）与 choose_endpoint 决策测试。"""
import unittest

from _util import LocalServer, make_handler, mf

BODY = b"hello-mirror-content-0123456789"


def row(kind, host, url, ok, status, latency, cause):
    return {"kind": kind, "host": host, "mode": "host-replace", "url": url,
            "result": {"ok": ok, "status": status, "latency_ms": latency, "cause": cause}}


class TestProbeClassification(unittest.TestCase):
    def test_status_codes_map_to_causes(self):
        # 同一 server 按 path 返回不同状态
        srv = LocalServer(make_handler(BODY, routes={
            "/ok": (200, BODY), "/range": (206, BODY),
            "/blocked": (403, b""), "/gone": (404, b""),
            "/auth": (401, b""), "/ratelimit": (429, b""), "/error": (500, b""),
        }))
        self.addCleanup(srv.close)
        base = f"http://{srv.host}"
        self.assertEqual(mf._probe_one(f"{base}/ok", 3)["cause"], "ok")
        self.assertEqual(mf._probe_one(f"{base}/range", 3)["cause"], "ok")
        self.assertEqual(mf._probe_one(f"{base}/blocked", 3)["cause"], "blocked")
        self.assertEqual(mf._probe_one(f"{base}/gone", 3)["cause"], "gone")
        self.assertEqual(mf._probe_one(f"{base}/auth", 3)["cause"], "auth")
        self.assertEqual(mf._probe_one(f"{base}/ratelimit", 3)["cause"], "blocked")
        self.assertEqual(mf._probe_one(f"{base}/error", 3)["cause"], "http")
        self.assertFalse(mf._probe_one(f"{base}/blocked", 3)["ok"])

    def test_conn_error_on_unused_port(self):
        # 本地未监听端口 → 连接失败；conn/timeout 依平台 connect 表现而异，语义同为"网络不可达"
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        r = mf._probe_one(f"http://127.0.0.1:{port}/x", 2)
        self.assertIn(r["cause"], ("conn", "timeout"))
        self.assertFalse(r["ok"])


class TestChooseEndpoint(unittest.TestCase):
    def test_picks_fastest_reachable(self):
        rows = [
            row("direct", "a.io", "http://a.io/f", False, 403, 100, "blocked"),
            row("mirror", "m1.com", "http://m1.com/f", True, 200, 300, "ok"),
            row("mirror", "m2.com", "http://m2.com/f", True, 200, 120, "ok"),
        ]
        chosen = mf.choose_endpoint(rows, "auto")
        self.assertEqual(chosen["host"], "m2.com")

    def test_blocked_auth_gone_never_selected_over_reachable_direct(self):
        rows = [
            row("direct", "a.io", "http://a.io/f", True, 200, 500, "ok"),
            row("mirror", "m1.com", "http://m1.com/f", True, 200, 50, "ok"),
        ]
        # auto 取延迟最小 → 镜像 m1
        self.assertEqual(mf.choose_endpoint(rows, "auto")["host"], "m1.com")
        # 显式 direct
        self.assertEqual(mf.choose_endpoint(rows, "direct")["host"], "a.io")
        # 显式 host
        self.assertEqual(mf.choose_endpoint(rows, "m1.com")["host"], "m1.com")

    def test_all_down_returns_none(self):
        rows = [
            row("direct", "a.io", "http://a.io/f", False, 403, 100, "blocked"),
            row("mirror", "m1.com", "http://m1.com/f", False, None, None, "timeout"),
        ]
        self.assertIsNone(mf.choose_endpoint(rows, "auto"))

    def test_mirror_ok_when_direct_blocked(self):
        # 直连被封(403)但镜像可达 → auto 选镜像（mip 同款场景）
        rows = [
            row("direct", "a.io", "http://a.io/f", False, 403, 100, "blocked"),
            row("mirror", "m1.com", "http://m1.com/f", True, 200, 200, "ok"),
        ]
        self.assertEqual(mf.choose_endpoint(rows, "auto")["host"], "m1.com")


if __name__ == "__main__":
    unittest.main()
