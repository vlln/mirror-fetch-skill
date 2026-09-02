# mirror-fetch CLI 参考（知识库查址/维护工具）

引擎：`scripts/mirror-fetch`（python3 stdlib，3.9+）。**本工具不发起任何网络请求**——
只读写知识库 JSON（默认 `$_S/configs/mirrors.json`，可用 `MIRROR_FETCH_CONFIG` 或
`--config` 覆盖）。下载请按 lookup 输出用 `curl -C -` 自行执行。

## 子命令

### `mirror-fetch lookup <URL 或 host>`

命中上游（含别名）→ 打印 howto + 候选镜像（含 verified 日期/note）；若输入是完整
URL，额外打印**每个候选镜像下可直接 curl 的 URL**（host-replace 已换域、prefix 已加前缀）。

> 下载建议带状态观测（分诊表以状态码为输入）：`curl -C - -L --fail -sS -o <dest>
> -w '\nHTTP=%{http_code} EFF=%{url_effective}\n' <镜像URL>`。`EFF=` 用于发现镜像
> "回源"（如 hf-mirror.com 2026-09-02 实测 308 → huggingface.co），确认实际端点。

未命中 → 列出现有上游 + 提示自行搜索后 `add` 入库。

### `mirror-fetch list`

列出全部上游 → 镜像（mode/verified），以及「已知镜像站服务目录」（含非 host-replace
型服务，如 ModelScope——只作线索，使用时自行确认差异）。

### `mirror-fetch search <关键词>`

按关键词匹配上游 host/别名、镜像 url/note、服务目录 name/url/for/note。

### `mirror-fetch add <upstream> <镜像url> [--mode host-replace|prefix] [--note ...] [--verified YYYY-MM-DD]`

把实测过的镜像写进知识库。治理规则（离线）：
- url 必须是 http(s)；mode ∈ {host-replace, prefix}；违反即报错不写入
- 同 upstream 同 url 去重（第二次报"已存在"，不重复写）
- `verified` 缺省 = 今天；手工传日期须 YYYY-MM-DD
- upstream 不存在时自动新建条目（aliases 空、howto 空——随后可手工补 howto）

**纪律：先实测再 add**（curl -I / 下载小文件验证），禁止把没验证的地址入库。

### `mirror-fetch validate`

知识库完整性检查（CI/测试用）：每 upstream 的 mirrors 非空、url http(s)、mode 枚举、
verified 日期格式；services 条目须有 name。违规 → 列出并退出码 1。

退出码：`0` 成功；`1` validate 发现违规；`2` 用法/参数错（含 add 的非法输入）。

## 知识库格式（configs/mirrors.json）

```json
{
  "format": "mirror-kb/1",
  "updated": "YYYY-MM-DD",
  "upstreams": {
    "huggingface.co": {
      "aliases": ["hf.co"],
      "howto": "把 huggingface.co 换成 hf-mirror.com，路径不变（host-replace）。",
      "mirrors": [
        {"url": "https://hf-mirror.com", "mode": "host-replace",
         "verified": "2026-09-02", "note": "实测日期/限制"}
      ]
    }
  },
  "services": [
    {"name": "ModelScope（魔搭）", "url": "https://modelscope.cn", "for": "模型",
     "note": "非 host-replace：需按仓库名搜索，用其 CLI/页面下载"}
  ]
}
```

- `mode`: `host-replace` = 换域名保路径（HF 类）；`prefix` = 镜像前缀 + 原完整 URL
  （GitHub proxy 类）。条目来源如果是继承的配置（如 mip configs/gip.yaml），在 note
  注明出处，`verified` 留空或写继承源的实测日——不要冒充"本环境实测"。
- `services`：信息性目录，可收录不能直接改写 URL 但"可能有用"的镜像站
  （ModelScope、registry mirror 指引等），note 说明与 host-replace 的差异。

## 环境变量

- `MIRROR_FETCH_CONFIG`：知识库路径替代（测试/临时库用）。

## 测试

```bash
python3 -m unittest discover -s tests -v   # 全离线（KB schema/lookup/mapped_urls/add 治理）
```
