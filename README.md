<h1 align="center">mirror-fetch-skill</h1>

<p align="center">
  <strong>内置镜像站地址知识库（KB）+ 查址工具，让 AI agent 在下载被墙/变慢时知道该用什么镜像。</strong><br/>
  面向文件/模型/仓库下载（HuggingFace、GitHub raw），给出镜像站地址、URL 映射方式与
  实测日期；下载由 agent 自己用 <code>curl -C -</code> 完成。知识库可搜索、可登记新镜像。
</p>

<p align="center">
  <a href="https://github.com/vlln/mirror-fetch-skill/stargazers"><img src="https://badgen.net/github/stars/vlln/mirror-fetch-skill?label=%E2%98%85" alt="GitHub stars" /></a>
  <img src="https://badgen.net/badge/license/MIT/blue" alt="MIT" />
  <img src="https://badgen.net/badge/spec/Agent%20Skills/8257D0" alt="Agent Skills spec" />
</p>

---

## 为什么是"知识库"而不是下载器

复现 agent 缺的不是下载能力（curl 人人会），是**该用哪个镜像站、镜像站怎么映射 URL**
的知识——尤其在国内网络下：HuggingFace 要换 hf-mirror.com、GitHub raw 要走 prefix
代理、gated 仓库镜像也拿不到（是凭据问题不是镜像问题）。这些知识散落在 mip/gip 配置与
各 run 的现场摸索里，本项目把它们收进一个带实测日期的知识库，agent 查址后自行下载。

定位差异（对比 [mip](https://github.com/vlln/mip)）：

| | mip / image-mirror-skill | 本项目 mirror-fetch |
|---|---|---|
| 对象 | OCI 镜像（docker pull 语义） | 文件/模型/仓库下载（curl 语义） |
| 主动性 | probe + pull + retag 全套 | **只查址**：lookup/search/list/add/validate，零网络请求 |
| 下载执行 | mip 自己做 | agent 自己 curl（续传纪律 `-C -`） |

## 内置镜像站地址（v0.2）

- **HuggingFace** → `hf-mirror.com`（host-replace；2026-09-02 实测可达）
- **GitHub / raw / release** → `gh-proxy.com`、`gh.llkk.cc`、`ghfast.top`、`ghproxy.net`
  （prefix 前缀式；清单继承自 mip configs/gip.yaml）
- **服务目录**（非 host-replace，线索型）：ModelScope（魔搭）、Docker Hub registry 镜像指引

## Installation

### [skit](https://github.com/vlln/skit) (Recommended)

```bash
skit install https://github.com/vlln/mirror-fetch-skill/tree/main/skills/mirror-fetch
```

### Manually

| Agent | Command |
|-------|---------|
| **Claude Code** | `cp -r skills/mirror-fetch .claude/skills/` |
| **Codex** | `cp -r skills/mirror-fetch ~/.codex/skills/` |

## Skills

| Skill | Description |
|-------|-------------|
| [`mirror-fetch`](skills/mirror-fetch/SKILL.md) | 查镜像站地址与 URL 映射（HF/GitHub 等），搜/登记镜像知识库；下载用 curl 自己做。 |

## Requirements

- `python3` ≥ 3.9（纯 stdlib，零依赖；工具本身不发网络请求）
- `curl`（下载由 agent 执行，工具不调用）

## Tests（全离线）

```bash
python3 -m unittest discover -s tests -v
```

覆盖：知识库 schema/validate、lookup（含别名命中）、host-replace/prefix URL 映射、
search、add 治理（去重/日期戳/非法输入拒绝）。

## License

MIT © 2026 vlln
