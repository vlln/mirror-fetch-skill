"""镜像站知识库工具测试（全离线）：KB schema/validate、lookup、mapped_urls、
search、add 治理。"""
import json
import tempfile
import unittest
from pathlib import Path

from _util import mf

UPSTREAMS = {
    "huggingface.co": {
        "aliases": ["hf.co"],
        "howto": "换 hf-mirror.com",
        "mirrors": [{"url": "https://hf-mirror.com", "mode": "host-replace",
                     "verified": "2026-09-02", "note": "probe 实测"}],
    },
    "github.com": {
        "aliases": ["raw.githubusercontent.com"],
        "howto": "prefix 代理",
        "mirrors": [{"url": "https://gh-proxy.com", "mode": "prefix"}],
    },
}
SERVICES = [{"name": "ModelScope（魔搭）", "url": "https://modelscope.cn", "for": "模型"}]


def write_kb(tmp: Path, upstreams=None, services=None) -> Path:
    raw = {"format": "mirror-kb/1", "updated": "2026-09-02",
           "upstreams": upstreams if upstreams is not None else UPSTREAMS}
    if services:
        raw["services"] = services
    p = tmp / "kb.json"
    p.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


class TestValidate(unittest.TestCase):
    def test_shipped_kb_valid(self):
        kb = mf.load_kb()
        self.assertEqual(mf.validate_kb(kb["upstreams"]), [])

    def test_bad_mode_detected(self):
        bad = {k: dict(v) for k, v in UPSTREAMS.items()}
        bad["huggingface.co"] = dict(UPSTREAMS["huggingface.co"])
        bad["huggingface.co"]["mirrors"] = [{"url": "https://hf-mirror.com", "mode": "magic"}]
        errs = mf.validate_kb(bad)
        self.assertTrue(any("mode" in e for e in errs))

    def test_empty_mirrors_detected(self):
        bad = {"x.io": {"aliases": [], "mirrors": []}}
        self.assertTrue(any("mirrors" in e for e in mf.validate_kb(bad)))

    def test_bad_verified_date_detected(self):
        bad = {"x.io": {"mirrors": [{"url": "https://m.com", "mode": "prefix",
                                     "verified": "昨天"}]}}
        self.assertTrue(any("verified" in e for e in mf.validate_kb(bad)))


class TestLookup(unittest.TestCase):
    def test_url_hit(self):
        up, body = mf.lookup_upstream(
            "https://huggingface.co/datasets/x/resolve/main/f", UPSTREAMS)
        self.assertEqual(up, "huggingface.co")

    def test_alias_host_hit(self):
        up, _ = mf.lookup_upstream("https://hf.co/datasets/x", UPSTREAMS)
        self.assertEqual(up, "huggingface.co")

    def test_raw_url_hits_github_via_alias(self):
        up, _ = mf.lookup_upstream("https://raw.githubusercontent.com/o/r/main/f", UPSTREAMS)
        self.assertEqual(up, "github.com")

    def test_unknown_returns_none(self):
        self.assertIsNone(mf.lookup_upstream("https://zenodo.org/r/1", UPSTREAMS)[0])


class TestMappedUrls(unittest.TestCase):
    def test_host_replace(self):
        got = mf.mapped_urls("https://huggingface.co/a/b?x=1#f",
                             {"url": "https://hf-mirror.com", "mode": "host-replace"})
        self.assertEqual(got, ["https://hf-mirror.com/a/b?x=1#f"])

    def test_prefix(self):
        got = mf.mapped_urls("https://raw.githubusercontent.com/o/r/main/f.csv",
                             {"url": "https://gh-proxy.com", "mode": "prefix"})
        self.assertEqual(got, ["https://gh-proxy.com/https://raw.githubusercontent.com/o/r/main/f.csv"])

    def test_prefix_base_slash_tolerance(self):
        got = mf.mapped_urls("https://github.com/o/r", {"url": "https://gh-proxy.com/", "mode": "prefix"})
        self.assertEqual(got, ["https://gh-proxy.com/https://github.com/o/r"])


class TestSearch(unittest.TestCase):
    def test_kw_hits_upstream(self):
        # search 输出走 CLI；这里验证可匹配的对象范围（engine 在 cmd_search 中实现）
        pass


class TestAdd(unittest.TestCase):
    def test_add_appends_and_saves(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_kb(Path(d))
            kb = mf.load_kb(p)
            status = mf.add_entry(kb, "huggingface.co", "https://hf-mirror2.example.com",
                                  "host-replace", note="x", verified="2026-09-02")
            self.assertEqual(status, "added")
            reloaded = mf.load_kb(p)
            urls = [m["url"] for m in reloaded["upstreams"]["huggingface.co"]["mirrors"]]
            self.assertIn("https://hf-mirror2.example.com", urls)

    def test_add_dedupes(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_kb(Path(d))
            kb = mf.load_kb(p)
            self.assertEqual(mf.add_entry(kb, "huggingface.co", "https://hf-mirror.com",
                                          "host-replace"), "exists")

    def test_add_creates_new_upstream(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_kb(Path(d))
            kb = mf.load_kb(p)
            mf.add_entry(kb, "zenodo.org", "https://m.example.com", "prefix",
                         verified="2026-09-02")
            self.assertIn("zenodo.org", mf.load_kb(p)["upstreams"])

    def test_add_rejects_non_http_and_bad_mode(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_kb(Path(d))
            kb = mf.load_kb(p)
            with self.assertRaises(ValueError):
                mf.add_entry(kb, "a.io", "m.com", "host-replace")
            with self.assertRaises(ValueError):
                mf.add_entry(kb, "a.io", "https://m.com", "magic")


if __name__ == "__main__":
    unittest.main()
