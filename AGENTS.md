# AGENTS.md — mirror-fetch-skill 开发说明（developer audience）

读者：维护/扩展本仓库的人。安装/使用/激活见 `README.md` 与 `skills/mirror-fetch/SKILL.md`；
本文件只讲设计与工程约定。

## 背景与血统

- 家族：仿 mip（`skill_project/mip`：configs/mip.yaml 镜像表 + probe 选最快 +
  rewrite/pull/retag），但 mip 面向 **OCI 镜像**（docker pull 语义），本工具面向
  **任意文件 URL 下载**（curl 语义）。
- 动机（bio-reproducer 校准失败分类学 v2）：S_MISJUDGE（bench-230 用错 URL 形式误判
  不可达）、S_DL_INCOMPLETE（210/234 可下载没下完即宣告 blocked）——agent 需要
  确定性 probe→fetch 通道 + 诚实的终态判定（ADR-0011 §2.1：传输层失败 ≠ 外部不可得）。
- 边界：**只治"公开文件慢/被封"**。401/407（gated/凭据）与 404（URL 错）不是镜像问题，
  引擎分别报 `auth`/`gone` 并引导正确处置——这是与失败分类学的直接接口。

## 架构

```
skills/mirror-fetch/
├── SKILL.md                  # agent 视角：触发/工作流/gotchas（<500 行）
├── configs/mirrors.json      # 上游 → 候选镜像表（唯一数据源，engine 读取）
├── scripts/mirror-fetch      # 引擎（单文件 python3 stdlib，无第三方依赖）
└── references/mirror-fetch-cli.md  # flags/JSON schema/退出码/新增上游/测试
tests/                        # 全离线测试（unittest discover）
```

引擎内聚顺序（与 SKILL.md workflow 对应）：config → URL → rewrite → probe → choose →
curl fetch → verify。**下载唯一入口是系统 `curl -C -`**（BL-024 续传纪律；不装 wget/aria2c）。
网络层（probe）与决策层（choose）分离：probe_fn 可注入，测试不打真实网络。

## 决策记录（为什么这样做）

| 决策 | 理由 |
|------|------|
| python3 stdlib-only，config 用 JSON | runtime 镜像 python3.10-slim/pixi 都要能跑且零依赖；JSON 用 `json` 内置解析，无 pyyaml 依赖（镜像表短、维护频率低） |
| 下载委托 curl 而非 urllib | 复用已验证的 `-C -`/Range/`--retry`/代理语义（BL-024 实测），urllib 续传要重造 |
| cause 分类 ok/blocked/auth/gone/timeout/conn/http | 直接映射失败分类学与 ADR-0011 终态：auth→凭据、blocked/gone→unavailable 候选、timeout/conn→not_attempted；防"未获取冒充不可获取" |
| probe 用 GET Range bytes=0-255（非 HEAD） | 部分服务器不支持 HEAD（405）；Range GET 同时验证"可下载"本身 |
| 每次 fetch 前 probe + 输出实际 endpoint | 镜像可用性漂移（防硬编码）；endpoint 落日志供跨批次可比性 |
| 空镜像表 = 仅直连 | 表外上游不报错，正常直连下载（fallback 语义明确） |

## 工程约定

- **纯离线测试**：`python3 -m unittest discover -s tests -v`。e2e 用本地双 HTTP server
  （`tests/_util.py` 的 LocalServer），curl 用 `MIRROR_FETCH_CURL` 打桩捕获 argv。
  禁止需要外网/真实镜像的测试（镜像可达性测试是维护者的手动步骤，见下）。
- **新增上游/镜像**：改 `configs/mirrors.json` → 本地 `mirror-fetch probe <真实URL>`
  实测通过（note 写实测日期）→ 跑全量测试（无新增测试则至少跑 rewrite/list 冒烟）→
  提交。禁止未实测即入库。
- **引擎无 .py 后缀**（可执行名），测试经 `importlib.machinery.SourceFileLoader` 加载
  （见 `tests/_util.py`），新测试文件沿用该模式。
- python 3.9 兼容：`from __future__ import annotations` 已开；不用 match/walrus。
- 本仓库是 bio-reproducer 的**上游独立项目**：改动先在本仓库自测，再通过技能集
  （fetch-skills.py/skills.lock.yaml）引入 runtime，不反向耦合 bio-reproducer 代码。

## 手动验证（维护者，有网时）

```bash
skills/mirror-fetch/scripts/mirror-fetch probe https://huggingface.co/datasets/x/resolve/main/README.md
skills/mirror-fetch/scripts/mirror-fetch check https://huggingface.co/xxx
```
