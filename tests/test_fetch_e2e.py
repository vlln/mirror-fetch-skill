"""离线端到端：本地 upstream + 本地 mirror 两个 HTTP server 驱动完整 fetch 路径。

场景：直连被封但镜像可达 → auto 走镜像；全部不可达 → 如实报失败；
curl 打桩验证 `-C -` 续传参数与选择端点；sha256 校验失败 → verify 阶段报错。
"""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from _util import LocalServer, make_handler, mf

CONTENT = b"genecorpus-30m-sample-" * 64  # 4KB 级别
SHA = hashlib.sha256(CONTENT).hexdigest()


def make_config(upstream_host, mirror_host):
    # 与 load_config 返回形状一致：cfg = {upstream: {aliases, mirrors}}
    return {upstream_host: {"aliases": [], "mirrors": [
        {"host": mirror_host, "mode": "host-replace", "note": "test"}]}}


class TestFetchE2E(unittest.TestCase):
    def test_direct_blocked_mirror_ok_fetch_via_mirror(self):
        upstream = LocalServer(make_handler(b"", routes={"/f": (403, b"forbidden")}))
        mirror = LocalServer(make_handler(CONTENT))
        self.addCleanup(upstream.close)
        self.addCleanup(mirror.close)
        url = f"http://{upstream.host}/f"
        cfg = make_config("127.0.0.1", mirror.host)

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.bin"
            res = mf.fetch(url, out, cfg, timeout=3)
            self.assertTrue(res["ok"], res)
            self.assertEqual(out.read_bytes(), CONTENT)
            self.assertEqual(res["sha256"], SHA)
            self.assertEqual(res["chosen"]["kind"], "mirror")
            self.assertEqual(res["chosen"]["host"], mirror.host)
            self.assertEqual(res["chosen"]["url"], f"http://{mirror.host}/f")

    def test_direct_ok_fetch_succeeds(self):
        upstream = LocalServer(make_handler(CONTENT))
        self.addCleanup(upstream.close)
        url = f"http://{upstream.host}/f"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.bin"
            res = mf.fetch(url, out, make_config("127.0.0.1", f"unused.invalid:{9999}"), timeout=3)
            # 镜像不可达、直连可达 → auto 落直连
            self.assertTrue(res["ok"], res)
            self.assertEqual(out.read_bytes(), CONTENT)
            self.assertEqual(res["chosen"]["kind"], "direct")

    def test_all_unreachable_reports_probe_stage(self):
        upstream = LocalServer(make_handler(b"", routes={"/f": (500, b"")}))
        self.addCleanup(upstream.close)
        url = f"http://{upstream.host}/f"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.bin"
            res = mf.fetch(url, out, make_config("127.0.0.1", "127.0.0.1:1"), timeout=2)
            self.assertFalse(res["ok"])
            self.assertEqual(res["stage"], "probe")
            causes = {r["result"]["cause"] for r in res["rows"]}
            self.assertIn("http", causes)  # 直连 500

    def test_sha256_mismatch_fails_at_verify(self):
        upstream = LocalServer(make_handler(CONTENT))
        mirror = LocalServer(make_handler(CONTENT))
        self.addCleanup(upstream.close)
        self.addCleanup(mirror.close)
        url = f"http://{upstream.host}/f"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.bin"
            res = mf.fetch(url, out, make_config("127.0.0.1", mirror.host),
                           timeout=3, sha256="0" * 64)
            self.assertFalse(res["ok"])
            self.assertEqual(res["stage"], "verify")

    def test_fetch_outside_table_still_downloads_direct(self):
        # 不在镜像表内的上游：仅直连，不报错
        upstream = LocalServer(make_handler(CONTENT))
        self.addCleanup(upstream.close)
        url = f"http://{upstream.host}/f"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.bin"
            res = mf.fetch(url, out, {}, timeout=3)  # 空表 = 无镜像，仅直连
            self.assertTrue(res["ok"], res)
            self.assertEqual(out.read_bytes(), CONTENT)


class TestCurlInvocation(unittest.TestCase):
    def _shim(self, d):
        """curl 打桩：argv 记 log；url 含 MF_TEST_FAIL_HOST 时以 401 失败；
        否则把 env 源内容写进 -o 目标。"""
        shim = Path(d) / "fake-curl"
        log = Path(d) / "curl.log"
        shim.write_text(
            "#!/usr/bin/env python3\n"
            "import sys, os\n"
            "args = sys.argv[1:]\n"
            "url = args[-1]\n"
            "with open(os.environ['MF_TEST_LOG'], 'a') as f:\n"
            "    f.write('|'.join(args) + '\\n')\n"
            "fail = os.environ.get('MF_TEST_FAIL_HOST', '')\n"
            "if fail and fail in url:\n"
            "    sys.stderr.write('curl: (56) The requested URL returned error: 401\\n')\n"
            "    sys.exit(22)\n"
            "out = args[args.index('-o') + 1]\n"
            "open(out, 'wb').write(os.environ['MF_TEST_SRC'].encode())\n"
        )
        shim.chmod(0o755)
        return shim, log

    def _fetch_with_shim(self, url, cfg, d, shim_env=None):
        """用打桩 curl 跑 fetch，隔离/清理环境变量。"""
        shim, log = self._shim(Path(d))
        out = Path(d) / "out.bin"
        old = {k: os.environ.get(k) for k in
               ("MIRROR_FETCH_CURL", "MF_TEST_LOG", "MF_TEST_SRC", "MF_TEST_FAIL_HOST")}
        os.environ["MIRROR_FETCH_CURL"] = str(shim)
        os.environ["MF_TEST_LOG"] = str(log)
        os.environ["MF_TEST_SRC"] = "stub-content"
        for k, v in (shim_env or {}).items():
            os.environ[k] = v
        try:
            res = mf.fetch(url, out, cfg, timeout=3)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return res, out, log

    def test_resume_flag_and_selected_url_passed_to_curl(self):
        upstream = LocalServer(make_handler(CONTENT))
        mirror = LocalServer(make_handler(CONTENT))
        self.addCleanup(upstream.close)
        self.addCleanup(mirror.close)
        url = f"http://{upstream.host}/f"
        with tempfile.TemporaryDirectory() as d:
            res, out, log = self._fetch_with_shim(
                url, make_config("127.0.0.1", mirror.host), Path(d))
            self.assertTrue(res["ok"], res)
            args = log.read_text().strip().split("|")
            self.assertIn("-C", args)  # 续传标志
            self.assertEqual(args[-1], f"http://{mirror.host}/f")  # 选中镜像 URL
            self.assertEqual(out.read_text(), "stub-content")

    def test_probe_ok_but_curl_401_falls_through_and_reports(self):
        # probe 显示镜像可达（Range 200）但真实 GET 401（反爬/凭据差异）：
        # fetch 应如实报失败并给 per-attempt 信息，不误报成功
        upstream = LocalServer(make_handler(b"", routes={"/f": (403, b"")}))
        mirror = LocalServer(make_handler(CONTENT))
        self.addCleanup(upstream.close)
        self.addCleanup(mirror.close)
        url = f"http://{upstream.host}/f"
        with tempfile.TemporaryDirectory() as d:
            res, out, log = self._fetch_with_shim(
                url, make_config("127.0.0.1", mirror.host), Path(d),
                shim_env={"MF_TEST_FAIL_HOST": mirror.host})
            self.assertFalse(res["ok"])
            self.assertEqual(res["stage"], "fetch")
            self.assertIn("401", res["error"])
            self.assertEqual(res["attempts"][0]["cause"], "auth")

    def test_first_candidate_fails_then_falls_back_to_second(self):
        # auto 按延迟选第一个（镜像），失败后应回退直连
        upstream = LocalServer(make_handler(CONTENT))
        mirror = LocalServer(make_handler(CONTENT))
        self.addCleanup(upstream.close)
        self.addCleanup(mirror.close)
        url = f"http://{upstream.host}/f"
        with tempfile.TemporaryDirectory() as d:
            res, out, log = self._fetch_with_shim(
                url, make_config("127.0.0.1", mirror.host), Path(d),
                shim_env={"MF_TEST_FAIL_HOST": mirror.host})
            self.assertTrue(res["ok"], res)
            self.assertEqual(res["chosen"]["kind"], "direct")
            self.assertEqual(len(res["attempts"]), 1)  # 镜像失败记录在案，直连成功


if __name__ == "__main__":
    unittest.main()
