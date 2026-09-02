# mirror-fetch CLI 参考

引擎：`scripts/mirror-fetch`（python3 stdlib，3.9+）。所有子命令支持 `--config <json>`
（默认 `$_S/configs/mirrors.json`）。下载委托系统 `curl`，需在 PATH（`requires.bins`）。

## 子命令

### `mirror-fetch list`

列出镜像表（上游 → 候选镜像 + mode + note）。URL 上游不在表内 → 无镜像可用。

### `mirror-fetch probe <url> [--timeout 8] [--json]`

直连 + 各候选镜像逐个 GET `Range: bytes=0-255` 探测（读 256B 即断）。

非 JSON 输出每行：
```
<kind:直连|镜像[mode]>  <host>  <OK|BLOCKED|AUTH(需凭据)|GONE(404)|TIMEOUT|CONN|HTTP n|OTHER>  <latency_ms>  <url>
```

`cause` 语义（`--json` 的 `rows[].result.cause`）：

| cause | 触发 | 处置建议 |
|-------|------|---------|
| `ok` | 200/206（重定向后终态） | 可选端点 |
| `blocked` | 403/429/451 | 封锁信号 → 试镜像；可判 unavailable（附状态码） |
| `auth` | 401/407 | **凭据问题（gated）**，镜像无效 → 需凭据注入通道 |
| `gone` | 404/410 | 源不存在/URL 形式错 → 先核对 URL 再判 unavailable |
| `timeout` / `conn` | 超时 / 连接失败 | 网络质量 → 续传重试；记 not_attempted 而非 unavailable |
| `http` | 其余 4xx/5xx | 按状态码人工裁决 |

### `mirror-fetch check <url> [--timeout 8] [--json]`

= probe + cause 汇总 + 结论（无可用端点时给出分类指引）。用于"不可获取 vs 未获取"
的终态判定。

### `mirror-fetch rewrite <url>`

列出直连与各候选重写 URL（mode: host-replace/prefix）。URL 不在表内会提示。

### `mirror-fetch fetch <url> -o <dest> [--mirror auto|direct|<host>] [--timeout 8]
[--no-resume] [--sha256 <hex>] [--json]`

probe → 选端点 → `curl --fail --location -sS --connect-timeout 15 --retry 3
--retry-all-errors [-C -] -o <dest> <url>` → 校验（--sha256 强制比对；否则非空）。

- `--mirror auto`（默认）：可达（cause=ok）候选中**延迟最小**者；直连被封但镜像可达
  时自动落镜像。`direct`：强制直连。`<host>`：强制指定镜像。
- `--no-resume`：去掉 `-C -`（正常不要用；续传是默认纪律）。
- 输出（非 JSON）：
  ```
  OK <dest>  <bytes>  <elapsed>s  via <直连|镜像 host (mode)>
  sha256 <hex>
  endpoint <实际使用的 URL>
  ```

退出码：`0` 成功；`2` 用法错；`3` 无可达端点（probe 阶段失败）；`4` 下载失败
（curl 非零，含 5xx）；`5` sha256 不符或产物为空（verify 阶段失败）。

## 配置格式（configs/mirrors.json）

```json
{
  "upstreams": {
    "huggingface.co": {
      "aliases": ["huggingface.co", "hf.co"],
      "mirrors": [
        {"host": "hf-mirror.com", "mode": "host-replace", "note": "2026-09-02 亲测可达"}
      ]
    }
  }
}
```

- `mirrors[].host` 可用 `"host:mode"` 简写；mode ∈ `host-replace`（换域保 path/query）
  | `prefix`（镜像域 + 原完整 URL，如 gh-proxy 型）。
- `aliases` 缺省为空；上游 key 与别名匹配 URL 的 host（端口剥离）。
- **新增上游**：加一个 key + 实测可达的镜像即生效（引擎通用，无代码改动）；
  镜像 `note` 记录实测日期。新镜像必须先 `probe` 验证再入库，禁止未实测即添加。

## 环境变量（测试/CI 打桩，正式流程勿设置）

- `MIRROR_FETCH_CURL`：curl 可执行路径替代（单测用假 curl 捕获 argv）。
- `MIRROR_FETCH_CONFIG`：镜像表路径替代。

## 测试

```bash
python3 -m unittest discover -s tests -v   # 全离线：单测 + 本地双 http server e2e
```
