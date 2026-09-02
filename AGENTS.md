# AGENTS.md — mirror-fetch-skill 开发说明（developer audience）

读者：维护/扩展本仓库的人。安装/使用/激活见 `README.md` 与 `skills/mirror-fetch/SKILL.md`；
本文件只讲设计与工程约定。

## 立场（2026-09-02 重构：v0.1 下载引擎 → v0.2 知识库）

- **v0.1 曾做主动下载引擎**（仿 mip：probe/choose/curl fetch/sha256），2026-09-02
  人类反馈后重构：agent 缺的不是下载能力（curl 人人会），是"该用哪个镜像、怎么映射 URL"
  的知识。故砍掉全部网络代码，保留**知识库 + 查址/维护工具**，下载交给 agent 自己 curl。
- 血统：镜像表数据继承自 mip（`configs/mip.yaml` 的 docker registry 表、
  `configs/gip.yaml` 的 GitHub prefix 表）与本环境实测（hf-mirror，2026-09-02
  Range probe）。mip 继续承担 OCI 镜像的主动下载（probe/pull/retag）；本 skill 与它
  正交，不重复造主动能力。

## 架构

```
skills/mirror-fetch/
├── SKILL.md                  # agent 视角：查址→自行 curl→登记纪律（<500 行）
├── configs/mirrors.json      # 知识库（唯一数据源）：upstreams + services
├── scripts/mirror-fetch      # 查址工具：lookup/list/search/add/validate（纯 stdlib，零网络）
└── references/mirror-fetch-cli.md  # 子命令/格式/治理规则
tests/                        # 全离线测试（unittest discover）
```

**关键约束：`scripts/mirror-fetch` 不得发起网络请求。** 网络相关功能（probe/下载）是
agent 的活；工具的产出是地址 + 映射 + 治理。若未来确需"验证镜像是否活着"的便利命令，
以维护者手动步骤（README/SKILL 指引）而非工具网络调用形式提供——先讨论再动，防过度主动。

## 决策记录

| 决策 | 理由 |
|------|------|
| 知识库 JSON + stdlib 查询工具 | 零依赖（runtime python3.10 可跑）；KB 短、结构固定 |
| mode ∈ {host-replace, prefix} 枚举 | 覆盖 HF（换域）与 GitHub proxy（前缀）两类真实用法；registry mirror / ModelScope 这类"不能直接改写 URL"的放 services 目录并注明差异，不硬塞进 mirrors |
| mirrors 条目带 `verified` 实测日期 | 镜像可用性漂移；日期让 agent 判断新鲜度；来源非本环境实测的（mip/gip 继承）不写 verified、note 注明出处——诚实标注是硬要求 |
| add 离线治理（去重/日期戳/mode 校验） | 让 agent 有能力"自己更新知识库"而不破坏格式；先实测再 add 的纪律写进 SKILL/CLI 文档 |
| 不臆造镜像 | 宁可缺失让 agent 搜索，不放未验证地址；docker registry 完整表由 mip 维护，KB 只放指引 |

## 工程约定

- 测试全离线：`python3 -m unittest discover -s tests -v`；禁止需要外网的测试。
  引擎无 .py 后缀，测试经 `importlib.machinery.SourceFileLoader` 加载（`tests/_util.py`）。
- 新增上游/镜像：改 `configs/mirrors.json` 或 `mirror-fetch add` → `validate` → 全量测试
  → 提交。**先实测再入库**；继承 mip/gip 的条目在 note 注明。
- python 3.9 兼容：`from __future__ import annotations` 已开；不用 match/walrus。
- 本仓库是 bio-reproducer 的上游独立项目：改动先在本仓库自测，再经技能集
  （fetch-skills.py/skills.lock.yaml）引入 runtime，不反向耦合 bio-reproducer 代码。

## 后续演进（候选，未定）

- 更多上游：Zenodo/NCBI/GEO **没有镜像生态**——若未来出现可用镜像（或中转服务）再收录，
  收录前提仍是实测通过。
- HF gated 凭据通道：是 harness 层问题（HF_TOKEN 注入），不是本 KB 的活；本 KB 只负责
  把 401 如实标出来（SKILL 分诊表）。
