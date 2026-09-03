# 🤝 VetAgent — 交接文档 (HANDOFF.md)

> 这是给接手的 AI 编码 agent（Claude Code）的产品+技术交接书。
> 产品负责人：简一（jianyi，Jia 的 AI 首席负责人）—— 你负责**开发实现**，我负责**总体规划、方向、质量把关**。我们协同，不是上下级。
> 目标：让你**零上下文损失**接上手，知道你该做什么、有哪些坑、有哪些原则、遇到问题找谁要资源。

---

## 0. 先说清角色分工（最重要的认知）

- **我是产品/项目负责人**（简一）：定方向、排优先级、把关质量、把关护城河、当你有更好的想法时支持决策。
- **你是开发 agent**（Claude Code）：负责**编码、部署、修复、测试**。你可以**质疑和优化**我的方向——我明确欢迎。
- **老板是 Jake**：最终拍板 + 提供资源（域名、Cloudflare、GitHub、服务器）。

**我们定的协作原则（请务必遵守）：**
1. **回归于悲观，不盲目乐观**——不要因为"实现了"就以为"成了"。用真实调用/测试验证。风控产品，**误报和漏报都是致命的**，宁可保守。
2. **主动思考更好的方法**——如果发现我有漏洞、有更聪明的方案、有隐藏成本，**直接说**，不要闷头执行一个次优方案。
3. **向 Jake/我寻求支持时，把资源选项说清楚**——域名、Cloudflare 额度、GitHub、服务器这些资源由 Jake 协调。你需要什么就明确说，不要自己憋着或擅自购买。
4. **fail-closed 是铁律**——风控工具拿不到数据时必须返回 `unknown`，**绝不**给乐观的中间值或仓位建议。
5. **区分事实 vs 判断**——实测数据是执行约束；你的推断降级为风险提示，不要用来否决方向。
6. **质量 > 数量**——做一个锋利单点，不 shotgun。

---

## 1. 产品是什么（一句话）

**VetAgent — 给 AI 代理的"买前安全检查"工具。** 在 agent 买入/持有/研究某个代币前，调它拿到一个**可执行的判断**（`low`/`medium`/`high`/`unknown`）+ 给 agent 的建议，而不是让 agent 去解读一堆数字。

不是让你自己炒币的工具，是**卖铲子**——帮想用 AI 做加密决策的人/团队先别踩坑。**赚钱靠信任和分发，不是靠行情。**

## 2. 生产环境（线上事实）

| 项 | 值 |
|---|---|
| 生产 URL | **https://vetagent.dev**（Cloudflare Worker，免ICP+自动HTTPS+全球CDN）|
| 备用 URL | https://vetagent.jake-gu95.workers.dev |
| MCP 端点 | **https://vetagent.dev/mcp**（streamable-http，已实测官方 FastMCP client 可连）|
| 落地页 | https://vetagent.dev/（VetAgent 品牌，SEO/GEO，JSON-LD）|
| 源码 repo | **github.com/jakegu1/vetagent**（Worker 版，主开发线）|
| 文档 repo | github.com/jakegu1/crypto-agent-risk（国内服务器版 + 运营文档）|
| Cloudflare 域名 | veteagent.dev（zone id 371490a6e5d239a023df9667bfe811b7）|
| Account ID | 3976e6f6f8237d5aa08543efa0e78887 |

> ⚠️ **凭证安全**：Cloudflare API Token 在 `.git-credentials` / 由 Jake 提供，**绝不能提交进 GitHub**。部署时用环境变量 `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`（见第6节）。

## 3. 技术栈 & 架构

**路径：`~/projects/vetagent-worker/`（服务器上）**

```
src/
  entry.py       — Worker 入口(必须叫 Default 类) + HTTP 路由
  risk.py        — 风控引擎(纯Python, 无重依赖) : assess / liquidity / new_pools
  mcp_server.py  — 手写 streamable-http MCP 端点 (JSON-RPC)
  landing.html   — 落地页
docs/
  server.json    — MCP registry 官方 manifest
  AGENT-INTEGRATION.md — 喂给 agent 的接入指南
pyproject.toml   — uv 项目, deps=[], dev=[workers-py, workers-runtime-sdk]
wrangler.jsonc   — Cloudflare 配置 (routes: vetagent.dev custom_domain)
```

**关键技术决策（不要随便推翻）：**
- **纯 Python + Workers 内置 `fetch()`**，不用 httpx——因为 Pyodide 对 httpx 依赖有兼容风险，`fetch()` 是官方推荐。
- **手写 MCP 端点**，不用官方 `mcp` 包——因为官方包依赖 `pydantic` 的 C 扩展，在 Cloudflare Python Workers **装不上**（实测）。手写 JSON-RPC 反而兼容官方 client。
- **模块化**：entry(路由) / risk(引擎) / mcp_server(协议)——单一代码源，避免重复。

## 4. 已有的坑（务必记住，别再踩）

| # | 坑 | 解法 |
|---|---|---|
| 1 | Worker 入口类**必须叫 `Default`**，否则报 "no fetch handler" | 类名固定 `class Default(WorkerEntrypoint)` |
| 2 | `request.url` 是**字符串**，不是对象 | 用 `from urllib.parse import urlparse` |
| 3 | 需要 `uv >= 0.12.3` | 已升级到 0.12.9；`uv self update` |
| 4 | 用 `pywrangler` 而非裸 `wrangler`（自动打包依赖）| `.venv/bin/pywrangler dev/deploy` |
| 5 | 冷启动首请求可能超时 | `_fetch_json` 已加指数退避重试（2次）|
| 6 | `mcp` 官方包在 Pyodide 装不上 | 手写 MCP 端点 |
| 7 | git push 走代理会卡(HTTP408)，直连更稳 | `git -c http.proxy= -c https.proxy= push` |
| 8 | GeckoTerminal 用 `eth`，chain_hint/DexScreener 用 `ethereum` | 链名统一映射（兜底分支已修）|
| 9 | 相对导入会失败 | 用绝对 `import risk` 而非 `from . import` |

## 5. 未完成 / 下一个优先级（按我定的）

**☑ 已完成**：P0 修复（选池/输入校验fail-closed/消除自相矛盾/无信号→unknown）、数据源容错(GeckoTerminal兜底)、生命周期信号、MCP端点、落地页、双repo同步。

**🔴 最高优先（我定的，别被"加功能"带偏）**：

1. **准确率基准（Claude 实测建议 + 我完全认同）** —— 拿 200 个已知 rug + 200 个正常代币跑一遍，公布**召回率和误报率**。这是风控产品建立信任的唯一方式，也是最好的推广素材。**当前没人做，第一个做就是护城河。**
2. **多链 GeckoTerminal 兜底**（未完全解决）—— 现在兜底写死 `eth`，MATIC 这种 polygon 主链代币兜底失效。需按链选 GT 网络。

**🟡 次优先（协议/规范，Claude 建议，值得做）**：
- MCP 用 `structuredContent`（别把 JSON 塞 text 里让客户端二次 parse）
- 精简 `evidence`（默认只回结论+3-5个证据，`verbose` 才全量）—— 降 70% 调用成本
- 浮点截断到 6 位有效数字
- 加 30-60s TTL 缓存（热门币冷启动 100ms）
- `chain_hint` 已生效，确认无回归

## 6. 如何部署（服务器上）

```bash
cd ~/projects/vetagent-worker
# 同步依赖
.venv/bin/pywrangler dev --port 8787            # 本地测试
# 部署（凭证用环境变量, 不写进 git）
export CLOUDFLARE_API_TOKEN=<Jake提供>
export CLOUDFLARE_ACCOUNT_ID=3976e6f6f8237d5aa08543efa0e78887
.venv/bin/pywrangler deploy
```
- 本地 dev 时 dexscreener 可能因代理不稳拿不到数据（**生产边缘直连没问题**，用生产验证）。
- 观测调用量：`npx wrangler tail vetagent --format json`

### 🖥️ 如果在你本地电脑开发（Jake 的机器）
1. `git clone https://github.com/jakegu1/vetagent.git && cd vetagent`
2. 装 `uv`（>=0.12.3）：`pip install uv` 或 `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. `uv sync`（装 workers-py + workers-runtime-sdk）
4. **Cloudflare 凭证**：向 Jake 要 `CLOUDFLARE_API_TOKEN`（只在本地设环境变量，**绝不写进 git**）。账号 Cloudflare 控制台 → My Profile → API Tokens 创建（权限 `Workers: Edit` + `Account: Read`，最小化）。或直接 `npx wrangler login`（OAuth，最安全）。
5. `npx wrangler dev` 本地测；`npx wrangler deploy` 上线。

> 有 `wrangler login` 的 OAuth 方式（最安全，不用传 token）和 API Token 方式（跨网络稳定）。远程服务器场景用 API Token 更稳，本地开发推荐 OAuth。

## 7. 找 Jake / 简一 要资源时

需要就明确说，Jake 会协调：
- **Cloudflare**（$5/月 Workers，目前远未用满）
- **域名**（vetagent.dev 已买，Zone ID 上表）
- **GitHub**（jakegu1 账号）
- **服务器**（124.222.120.49，已有国内版 crypto-agent-risk）

## 8. 关键参考文件
- `docs/server.json` — MCP registry 格式
- `docs/AGENT-INTEGRATION.md` — 给 agent 的接入文档
- `reference/projects.md`（在 Hermes 侧，非 repo）— 项目状态速查
