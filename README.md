<h1 align="center">mirror-fetch-skill</h1>

<p align="center">
  <strong>内置镜像站地址知识库（KB）+ 查址工具，解决"网络受限时下载知名资源"这一大类问题。</strong><br/>
  在慢速、超时或被墙的环境里从 HuggingFace、GitHub 等拉取数据集、模型权重、代码文件时，
  告诉你该用哪个镜像站、URL 怎么映射、上次实测是什么时候——而不是让你现场摸索或瞎猜。
</p>

<p align="center">
  <a href="https://github.com/vlln/mirror-fetch-skill/stargazers"><img src="https://badgen.net/github/stars/vlln/mirror-fetch-skill?label=%E2%98%85" alt="GitHub stars" /></a>
  <img src="https://badgen.net/badge/license/MIT/blue" alt="MIT" />
  <img src="https://badgen.net/badge/spec/Agent%20Skills/8257D0" alt="Agent Skills spec" />
</p>

---

## 它解决什么问题

**一类普遍问题**：任何 AI agent、脚本或开发者，在受限网络（国内网络最常见，也包括
公司内网、沙箱、容器等出口受限环境）从 HuggingFace、GitHub 等上游拉资源——数据集、
模型权重、仓库文件、release——会遇到三种混淆：

1. **不知道该用哪个镜像站**：hf-mirror.com？gh-proxy.com？每个上游的可用镜像都不一样，
   而且镜像站经常漂移/停服/换域名。
2. **不知道怎么映射 URL**：有的镜像换域名保路径（host-replace），有的要加前缀
   （prefix），有的根本不是直接改写 URL（ModelScope 要按仓库名另搜）。
3. **分不清失败原因**：慢/超时是网络问题该走镜像，404 往往是 URL 写错，401/407 是
   gated/凭据问题——镜像救不了后两种，误判会浪费大量时间。

这个 skill 把这些**知识**收进一个带实测日期的知识库：查址、搜索、登记新镜像都由
`mirror-fetch` 工具完成（**零网络请求，纯离线**）；拿到地址后，下载由你自己用
`curl -C -` 执行——因为下载能力你本来就有，稀缺的是知识。

本项目最初源于论文复现系统校准跑批的教训（下载被墙却误报"数据不可获取"），但解决
的问题本身是通用的，适用于任何要下载 HF/GitHub 等资源的 agent 或工作流。

## 定位差异（对比 [mip](https://github.com/vlln/mip)）

| | mip / image-mirror-skill | 本项目 mirror-fetch |
|---|---|---|
| 对象 | OCI 镜像（docker pull 语义） | 文件/模型/仓库下载（curl 语义） |
| 主动性 | probe + pull + retag 全套 | **只查址**：lookup/search/list/add/validate，零网络请求 |
| 下载执行 | mip 自己做 | agent/脚本自己 curl（续传纪律 `-C -`） |

## 内置镜像站地址（v0.2）

- **HuggingFace** → `hf-mirror.com`（host-replace；2026-09-02 实测可达）
- **GitHub / raw / release** → `gh-proxy.com`、`gh.llkk.cc`、`ghfast.top`、`ghproxy.net`
  （prefix 前缀式；清单继承自 mip configs/gip.yaml，其中三个已转本环境实测）
- **服务目录**（非 host-replace，线索型）：ModelScope（魔搭）、EBI-ENA/Aspera
  （SRA/GEO 官方加速）、jsDelivr（GitHub raw 替代端点）、GitHub520 hosts、Docker
  Hub registry 镜像指引等

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
- `curl`（下载由使用者执行，工具不调用）

## Tests（全离线）

```bash
python3 -m unittest discover -s tests -v
```

覆盖：知识库 schema/validate、lookup（含别名命中）、host-replace/prefix URL 映射、
search、add 治理（去重/日期戳/非法输入拒绝）。

## License

MIT © 2026 vlln
