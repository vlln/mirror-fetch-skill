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
        """curl 打桩：把 argv 记到 log，把 env 源内容写进 -o 目标。"""
        shim = Path(d) / "fake-curl"
        log = Path(d) / "curl.log"
        shim.write_text(
            "#!/usr/bin/env python3\n"
            "import sys, os\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['MF_TEST_LOG'], 'a') as f:\n"
            "    f.write('|'.join(args) + '\\n')\n"
            "out = args[args.index('-o') + 1]\n"
            "open(out, 'wb').write(os.environ['MF_TEST_SRC'].encode())\n"
        )
        shim.chmod(0o755)
        return shim, log

    def test_resume_flag_and_selected_url_passed_to_curl(self):
        upstream = LocalServer(make_handler(CONTENT))
        mirror = LocalServer(make_handler(CONTENT))
        self.addCleanup(upstream.close)
        self.addCleanup(mirror.close)
        url = f"http://{upstream.host}/f"
        with tempfile.TemporaryDirectory() as d:
            shim, log = self._shim(Path(d))
            out = Path(d) / "out.bin"
            old = os.environ.get("MIRROR_FETCH_CURL")
            os.environ["MIRROR_FETCH_CURL"] = str(shim)
            os.environ["MF_TEST_LOG"] = str(log)
            os.environ["MF_TEST_SRC"] = "stub-content"
            try:
                res = mf.fetch(url, out, make_config("127.0.0.1", mirror.host), timeout=3)
            finally:
                if old is None:
                    os.environ.pop("MIRROR_FETCH_CURL", None)
                else:
                    os.environ["MIRROR_FETCH_CURL"] = old
                os.environ.pop("MF_TEST_LOG", None)
                os.environ.pop("MF_TEST_SRC", None)
            self.assertTrue(res["ok"], res)
            args = log.read_text().strip().split("|")
            self.assertIn("-C", args)  # 续传标志
            self.assertEqual(args[-1], f"http://{mirror.host}/f")  # 选中镜像 URL
            self.assertEqual(out.read_text(), "stub-content")


if __name__ == "__main__":
    unittest.main()
