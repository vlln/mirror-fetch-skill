"""URL 规范化 / 镜像表查找 / rewrite 模式（host-replace、prefix）测试。"""
import json
import tempfile
import unittest
from pathlib import Path

from _util import mf

HF = "https://huggingface.co/datasets/Genecorpus-30M/Genecorpus-30M/resolve/main/README.md"
CFG = {"huggingface.co": {
    "aliases": ["hf.co", "huggingface.com"],
    "mirrors": [
        {"host": "hf-mirror.com", "mode": "host-replace"},
        {"host": "gh-proxy.example.com", "mode": "prefix", "note": "x"},
    ],
}}


class TestNormalize(unittest.TestCase):
    def test_adds_https_default(self):
        self.assertEqual(mf.normalize_url("huggingface.co/a/b"), "https://huggingface.co/a/b")

    def test_keeps_explicit_scheme(self):
        self.assertEqual(mf.normalize_url("http://x.io/a"), "http://x.io/a")

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            mf.normalize_url("not a url")


class TestLookup(unittest.TestCase):
    def test_exact_host(self):
        up, body = mf.lookup_upstream(HF, CFG)
        self.assertEqual(up, "huggingface.co")

    def test_alias_host(self):
        up, _ = mf.lookup_upstream("https://hf.co/datasets/x", CFG)
        self.assertEqual(up, "huggingface.co")

    def test_unknown_upstream(self):
        up, body = mf.lookup_upstream("https://ftp.ncbi.nlm.nih.gov/a.tar", CFG)
        self.assertIsNone(up)

    def test_port_stripped_for_lookup(self):
        # 本地 e2e：host 带端口也应命中上游 key
        cfg = {"127.0.0.1": {"aliases": [], "mirrors": [{"host": "m.test", "mode": "host-replace"}]}}
        up, _ = mf.lookup_upstream("http://127.0.0.1:8080/f", cfg)
        self.assertEqual(up, "127.0.0.1")


class TestRewrite(unittest.TestCase):
    def test_host_replace_keeps_path_query_fragment(self):
        url = "https://huggingface.co/datasets/x/y/resolve/main/f.csv?download=true#L1"
        out = mf.rewrite_url(url, {"host": "hf-mirror.com", "mode": "host-replace"})
        self.assertEqual(
            out,
            "https://hf-mirror.com/datasets/x/y/resolve/main/f.csv?download=true#L1")

    def test_host_replace_preserves_scheme(self):
        out = mf.rewrite_url("http://huggingface.co/f", {"host": "m.com", "mode": "host-replace"})
        self.assertEqual(out, "http://m.com/f")

    def test_prefix_mode_wraps_original_url(self):
        out = mf.rewrite_url("https://huggingface.co/f/g", {"host": "proxy.example.com", "mode": "prefix"})
        self.assertEqual(out, "https://proxy.example.com/https://huggingface.co/f/g")

    def test_list_candidates_in_config_order(self):
        cands = mf.list_candidates(HF, CFG)
        self.assertEqual([c["mode"] for c in cands], ["host-replace", "prefix"])
        self.assertEqual(cands[0]["url"], "https://hf-mirror.com" + HF.split("huggingface.co")[1])

    def test_list_candidates_empty_when_unknown(self):
        self.assertEqual(mf.list_candidates("https://zenodo.org/r/1", CFG), [])


class TestConfigLoad(unittest.TestCase):
    def test_loads_shipped_config(self):
        cfg = mf.load_config()  # 默认随脚本的 configs/mirrors.json
        self.assertIn("huggingface.co", cfg)
        m = cfg["huggingface.co"]["mirrors"][0]
        self.assertEqual(m["host"], "hf-mirror.com")
        self.assertEqual(m["mode"], "host-replace")

    def test_missing_mirrors_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text(json.dumps({"upstreams": {"x.io": {"aliases": []}}}))
            with self.assertRaises(SystemExit):
                mf.load_config(p)

    def test_unknown_mode_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text(json.dumps({"upstreams": {"x.io": {"mirrors": ["m.com:magic"]}}}))
            with self.assertRaises(SystemExit):
                mf.load_config(p)

    def test_bad_json_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text("{not json")
            with self.assertRaises(SystemExit):
                mf.load_config(p)


if __name__ == "__main__":
    unittest.main()
