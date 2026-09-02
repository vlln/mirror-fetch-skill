---
name: mirror-fetch
description: >
  Use this skill when a download (dataset, model weights, repo files) from
  huggingface.co, github.com / raw.githubusercontent.com — or any upstream in
  the built-in mirror knowledge base — is slow, times out, or is blocked:
  look up the mirror site addresses and URL-mapping rules, then download
  yourself with curl. Also use it to search the built-in mirror-site catalog
  or to record a newly verified mirror into the knowledge base. This is a
  knowledge base, not a downloader: it never issues network requests.

# Optional: metadata ────────────────────────────────
license: MIT
metadata:
  author: vlln
  version: "0.2.0"

# Optional: skit requirements ───────────────────────
requires:
  bins:
    - curl
---

# mirror-fetch（镜像站知识库）

复现/下载慢的根因常常不是"不会下载"，而是"不知道该用哪个镜像站、镜像站怎么映射
URL"。本 skill 提供**镜像站地址知识库**：`$_S/configs/mirrors.json` 内置上游 →
候选镜像（含映射方式与实测日期），工具 `$_S/scripts/mirror-fetch` 只做查址/搜索/
维护（**不发起任何网络请求**）；下载由 agent 自己用 `curl -C -` 执行。

## 什么时候用

- huggingface.co / github.com 相关下载慢、超时、Connection reset、403/429（先查镜像再重试）
- 需要确认"到底有没有可用镜像"再决定怎么下载
- agent 自行搜到一个新镜像站、想验证并**登记进知识库**（供以后复用）

## Workflow

1. **查址**：`mirror-fetch lookup <上游URL或host>` —— 命中则打印 howto + 候选镜像 +
   具体可用 URL（host-replace 已换好域 / prefix 已加前缀）。
2. **照 howto 自己下载**（工具不发网络，下载是你的活）——curl 模板**统一带
   `-sS` 与 `-w` 状态观测**（分诊表以 HTTP 状态码为输入；`--fail` 只给 exit 22，
   无法区分 401/404/403）：
   ```bash
   curl -C - -L --fail -sS -o <dest> -w '\nHTTP=%{http_code} EFF=%{url_effective}\n' <镜像URL>
   ```
   - host-replace 型（HF → hf-mirror.com）：URL 已换域；下载后看 `EFF=` 确认实际端点
   - prefix 型（GitHub 系）：`https://gh-proxy.com/<原完整URL>`；git clone：
     `git clone https://gh-proxy.com/https://github.com/o/r.git`
   - **续传纪律**：中断后用同一命令同一输出路径重跑（`-C -` 幂等续传），不要装 wget/aria2c
   - **候选镜像不通就试下一个**（ghproxy 类站漂移快；`lookup` 已列出全部候选）
3. **知识库没有该上游**：`mirror-fetch list` 看全表 → `mirror-fetch search <关键词>`
   看服务目录（含 ModelScope 这类非 host-replace 项）→ 仍无则自行搜索可用镜像，
   **实测通过后** `mirror-fetch add <upstream> <镜像url> --note <实测日期/限制>` 入库
   （离线治理：去重 + verified 日期戳 + mode 校验）。
4. **镜像疑似失效**：看条目 `verified` 日期判断新鲜度 → 直接 probe 该镜像站
   （curl -I 或下小文件）→ 确认失效则换其他候选或另寻新镜像入库。

## 下载前的分诊（镜像救不了的情况，别浪费时间）

| 症状 | 判定 | 处置 |
|------|------|------|
| 慢/超时/SSL 断/403 | 网络或封锁 | 查镜像 → 用镜像 URL 下载 |
| **404 / Repository Not Found** | URL 形式错（S_MISJUDGE 型） | **先核对 URL**：models vs datasets 路径、缺 `/resolve/main/`、缺 `/datasets/`——镜像救不了 404 |
| **401/407**（HF gated 仓库等） | 凭据问题 | 镜像同样 401 → 需 token/凭据通道；如实报告，不得称"不可获取" |
| 镜像表外且无镜像（Zenodo/figshare/NCBI-GEO/Kaggle/Dryad/OSF、论文复现用 GitLab 仓库等） | 无镜像生态 | 续传重试/换网络/换时段；**SRA/GEO 大文件**改走 EBI-ENA 官方镜像或 NCBI Aspera，Zenodo 用 `zenodo_get` 断点续传（见 services 目录） |
| OCI 镜像（docker pull） | 不是本 KB 的活 | 走 `mip`（image-mirror-skill，含 probe/镜像表） |

## 维护纪律（更新知识库时）

- **只收实测过的地址**：亲自 curl/下载验证后再 `add`；`verified` 记实测日期
  （来源 mip/gip 配置的条目在 note 注明出处，不冒充"本环境实测"）
- **不要臆造镜像**：宁可 knowledge base 缺条目让 agent 自己搜，也不放没验证的地址
- **mode 只能 host-replace 或 prefix**（换域保路径 / 前缀式）；"同名仓库但 API 不同"
  的服务（如 ModelScope）放 `services` 目录而非 upstreams，note 说明差异
- Docker Hub 类 registry 镜像表由 mip 维护（本 KB services 目录只放指引，不放清单）

## Gotchas

- 本工具**零网络请求**——它给的是知识，不是结果；下载结果以你的 curl 实测为准。
- **镜像可能"回源"**：2026-09-02 实测 hf-mirror.com 对文件 GET 返回 308 重定向回
  huggingface.co（实际落到源站）——下载后看 `EFF=%{url_effective}` 确认实际端点；
  若源站 401/风控，"走镜像"同样拿不到（如实归类，别误报镜像失效）。
- 镜像可用性会漂移：条目的 `verified` 只是上次实测日期，用前自行确认；候选不通试下一个。
- 404 ≠ 网络问题：先查 URL 与来源（论文/数据声明/entry bundle）是否逐字一致。
- gated（401）≠ 镜像问题：任何镜像都拿不到，需要凭据通道。
- GitHub raw 走 prefix 代理；`github.com` 条目别名已含 `raw.githubusercontent.com` 等，
  lookup 任意一个都会命中同一组镜像。
