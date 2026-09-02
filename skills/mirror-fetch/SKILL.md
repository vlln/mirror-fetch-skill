---
name: mirror-fetch
description: >
  Use this skill when downloading files (datasets, model weights, supplementary
  data) from huggingface.co — or any upstream listed in the mirror table — is
  slow, times out, or is blocked: probe reachable domestic mirrors, rewrite the
  URL, resume the download with curl -C -, and verify the result. Activate when
  a download fails with network errors, when the agent wants to check whether a
  source is truly unreachable before declaring it unavailable, or when asked to
  accelerate a large file download from a mirror-supported upstream.

# Optional: metadata ────────────────────────────────
license: MIT
metadata:
  author: vlln
  version: "0.1.0"

# Optional: skit requirements ───────────────────────
requires:
  bins:
    - curl
---

# mirror-fetch

Use this skill when a data/model download from an upstream in the mirror table
(`$_S/configs/mirrors.json`; currently `huggingface.co`) is **slow, times out,
or returns network errors**. The engine probes the direct URL and each candidate
mirror, picks a reachable endpoint, downloads with `curl -C -` resume, and
verifies. It also answers the honest question behind every failed download:
*is the source unavailable, or did we just not get it?*

Script: `$_S/scripts/mirror-fetch`（python3 stdlib，无第三方依赖；下载委托系统
`curl`）。配置表：`$_S/configs/mirrors.json`。CLI 全量参考：`$_S/references/mirror-fetch-cli.md`
（flags / JSON 输出 / 退出码 / 新增上游）。

## When to use

- `curl`/下载失败：超时、`Connection reset`、SSL EOF、403/429/451（触发镜像）
- 下载极慢（如 5-25 MB/min 级别的 HuggingFace 大文件）——先用 `mirror-fetch check` 量化
- 判定一个数据源"不可获取 vs 未获取"（对照 ADR-0011 终态类别：`unavailable` 需真实访问墙
  证据；传输层失败是 `not_attempted`，**不是**不可获取）——用 `mirror-fetch check`
- 大文件下载提速（已知镜像表内的上游）

## 先分清问题类型（避免误用）

| 症状 | 判定方法 | 是否 mirror-fetch 的活 |
|------|---------|----------------------|
| 慢 / 超时 / SSL 断 / 403 封锁 | `mirror-fetch probe <url> --json` | ✅ 是 |
| **404** | `mirror-fetch check` 报 `gone` → **先核对上游 URL 形式**（如 `models` vs `datasets` 路径、缺 `/resolve/main/`、`/datasets/` 前缀缺失），再怀疑网络 | ⚠️ 镜像治不了 404——404 通常是 URL 错（S_MISJUDGE 型） |
| **401/407**（gated 仓库如 UNI 权重） | `mirror-fetch check` 报 `auth` | ❌ 不是——gated 是凭据问题，镜像无效；如实报"需凭据注入通道"（E_CONTROLLED/I_*），**不得声称不可获取** |
| 镜像表外的上游（NCBI/GEO/Zenodo/figshare） | `mirror-fetch list` 无该上游 | ❌ 无镜像可走；只能续传重试/换网络，见 Gotchas |

## Workflow

1. **量化问题**：`mirror-fetch probe <url> --json` → 看直连与各镜像的
   `cause`（ok/blocked/auth/gone/timeout/conn）与延迟。
2. **能走镜像就走镜像**：`mirror-fetch fetch <url> -o <dest> [--sha256 <hex>]`。
   auto 模式在可达候选中选延迟最小者；直连被封(403)但镜像可达时会自动落镜像。
3. **续传即重跑**：网络中途断开后，**用同一命令同一输出路径重跑**——引擎带
   `curl -C -`，幂等续传，不需要清掉半截文件。
4. **校验**：给了 `--sha256` 则下载后强制比对（不符 → verify 阶段失败，退出码 5）；
   没给则至少非空。产物非空是"已获取"的最低证据（ADR-0011 §2.1）。
5. **如实记录 endpoint**：fetch 输出含 `chosen.url`（实际端点）——把它写进获取日志，
   供跨批次可比性（用了哪个镜像/直连，同一次运行内可能不同）。
6. **判定落盘**：仍全部不可达时，用 `mirror-fetch check` 的 cause 分类决定终态：
   `auth` → 凭据问题；`blocked`/`gone` 需附真实状态码 → 可判 `unavailable`；
   仅 `timeout`/`conn` → 只能记 `not_attempted`（"未获取"，非"不可获取"）。

## Gotchas

- **镜像只治"慢/被封的公开文件"，不治 gated**：401/407 是凭据问题（如 HF gated 仓库），
  任何镜像都返回同样的 401。报告为"需凭据"，不要写"网络不可达"或"不可获取"。
- **404 ≠ 网络问题**：`gone` 时先检查 URL 是否与来源（论文/数据声明/entry bundle）逐字
  一致——`models` 与 `datasets` 的 path 不同、HF 需要 `/resolve/main/<file>`、`/datasets/`
  前缀不能省。改形式后先 `probe` 再下载（历史教训：bench-230 用错 URL 形式误判不可达）。
- **镜像可用性会漂移**：每次使用前 `probe`，不要凭记忆硬编码某个镜像可用；表内
  `note` 只记录上次实测日期。
- **续传纪律**：`curl -C -`（Range/HTTP 206）在 NCBI/HF 均实测可用；**不要**为续传安装
  wget/aria2c（BL-024）。引擎已内置 `-C -`，除非 `--no-resume`。
- **不要发明镜像**：只使用 `configs/mirrors.json` 表内候选；新镜像需实测后由维护者
  加表（见 `references/mirror-fetch-cli.md` 的新增上游一节）。
- **probe 通过 ≠ 下载必成**：probe 是可达性信号（Range 小请求），真实 GET（curl）可能
  才暴露 401/403（反爬/凭据/UA 差异，2026-09-02 实测：hf-mirror Range 200 但完整 GET 401）。
  **终态判定以 `fetch` 的 `attempts[].cause` 为准**，probe/check 只作初筛。
- **下载完成才算已获取**：`Download complete`/文件大小符合 Content-Length/`sha256` 一致
  三选一作为完成信号；半截文件 + 中断日志 ≠ 已获取。
- 引擎 stdlib-only（python3.9+），下载委托系统 `curl`；`MIRROR_FETCH_CURL`/
  `MIRROR_FETCH_CONFIG` 环境变量用于打桩/自定义配置（测试与 CI 用，勿在正式流程设置）。
