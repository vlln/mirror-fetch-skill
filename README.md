<h1 align="center">mirror-fetch-skill</h1>

<p align="center">
  <strong>Generic mirror-aware file downloader for AI agents.</strong><br/>
  When huggingface.co (or any mirror-table upstream) downloads are slow, time out,
  or are blocked, mirror-fetch probes reachable domestic mirrors, rewrites the URL,
  resumes with <code>curl -C -</code>, verifies the file, and records which endpoint
  was actually used — so agents stop misreporting "unavailable" for sources that
  were merely slow.
</p>

<p align="center">
  <img src="https://badgen.net/badge/license/MIT/blue" alt="MIT" />
  <img src="https://badgen.net/badge/spec/Agent%20Skills/8257D0" alt="Agent Skills spec" />
</p>

---

## What it does

`mirror-fetch` is a config-driven engine (same family as
[`mip`](https://github.com/vlln/mip), but for **file/URL downloads** instead of OCI
images): an upstream→mirror table, a probe step that classifies reachability
(`ok/blocked/auth/gone/timeout/conn`), URL rewriting (`host-replace`/`prefix`),
resumable download via system `curl -C -`, and sha256 verification.

It exists because of a measured failure mode in bio-reproducer calibration runs:
downloads that were slow or blocked got reported as "unavailable" (S_MISJUDGE /
S_DL_INCOMPLETE in `calibration-failure-taxonomy-v2.md`), when a mirror or a retry
would have succeeded. The skill gives agents a deterministic probe→fetch path and
an honest terminal-state classification.

## Installation

### [skit](https://github.com/vlln/skit) (Recommended)

```bash
skit install ./mirror-fetch-skill --skill mirror-fetch
```

### Manually

| Agent | Command |
|-------|---------|
| **Claude Code** | `cp -r skills/mirror-fetch .claude/skills/` |
| **Codex** | `cp -r skills/mirror-fetch ~/.codex/skills/` |

## Skills

| Skill | Description |
|-------|-------------|
| [`mirror-fetch`](skills/mirror-fetch/SKILL.md) | Probe domestic mirrors for slow/blocked file downloads (HF first), fetch with resume, verify, and classify "unavailable vs not-attempted" honestly. |

## Requirements

- `python3` ≥ 3.9（引擎纯 stdlib，无第三方依赖）
- `curl`（下载委托，含 `-C -` 续传与 Range 支持）

## Tests（全离线）

```bash
python3 -m unittest discover -s tests -v
```

单测覆盖 URL 重写/配置校验/端点选择；e2e 用本地双 HTTP server（直连 403 + 镜像可达、
全不可达、sha256 校验失败、curl 打桩验证 `-C -`）驱动完整 fetch 路径，不需要外网。

## License

MIT © 2026 vlln
