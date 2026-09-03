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
| 10 | **Windows 上 pywrangler 跑不起来** —— 它要建 emscripten 的 pyodide venv，Windows 不支持 | 用 CI 部署（`.github/workflows/deploy.yml`）；应急可走 WSL：`XDG_CONFIG_HOME=/mnt/c/Users/<你>/AppData/Roaming/xdg.config uv run pywrangler deploy` 复用 Windows 已有的 OAuth 会话 |
| 11 | 裸 `wrangler deploy` 能构建成功但**部署后 Worker 启动即崩** —— `ModuleNotFoundError: No module named 'workers'`，因为它不 vendor workers-py | 一律用 `uv run pywrangler deploy`。dry-run 通过**不代表**能跑，它不校验运行时导入 |
| 12 | `git pull origin master` 在别的分支上会把 master 合进当前分支，本地 master 仍是旧的 | 部署前先 `git rev-parse --short master origin/master` 对一下，别对着旧代码发布 |

## 5. 未完成 / 下一个优先级

### ⚠️ 关于上一轮"已完成"的更正（2026-09-03）

上一版本这里写着「☑ 已完成：P0 修复（选池/输入校验/fail-closed/无信号→unknown）」。
**这个记录不准确**，实测后发现：

| 声称已修 | 实际情况 |
|---|---|
| 选池修复 | 只打在 `assess()` 上，`liquidity()` 完全没改——线上把 USDC 报成 $0.00097 |
| 输入校验 | 同上，`liquidity()` 无任何校验 |
| 无信号→unknown | `unknown` 分支实际不可达，全数据源失败时返回 medium |
| Honeypot 检测 | **从来没工作过**：读的是 `simulationResult.isHoneypot`，而上游把它放在 `honeypotResult` 里；该键不存在 → None → False → 恒定输出「ok / 非 Honeypot」 |

根因不是粗心，是**没有测试**。当"Verified"只意味着手动跑了两三个地址，
漏掉一条代码路径是必然而不是偶然。

**因此本轮引入的第一条纪律：**

> 任何 commit 声称修好了什么，必须有一个对应的测试用例，
> 且该用例在修复前是红的。`tests/` 下每个用例都对应一个真实发生过的线上缺陷。

```bash
python tests/test_risk.py              # 71 项，离线，基于真实上游快照
python tests/test_mcp.py               # 41 项，MCP 协议一致性
python tests/test_upstream_contract.py # 41 项，真实联网，验证依赖的 JSON 路径还在
```

第三个尤其重要：**当初的 honeypot bug 只有契约测试能抓到**——
它的本质是"读了一个上游不存在的键"，任何 mock 测试都发现不了。
CI 已配置（`.github/workflows/test.yml`），前两个套件红了就不许合。

**☑ 本轮实际完成**：honeypot 键路径修复 + 上游 summary.risk/flags/contractCode 接入、
仿真失败 fail-closed、`liquidity()` 补齐校验与选池、分叉链选池防护、交易对年龄修复、
评分模型改为"最坏信号主导"、Solana 路径重写（score_normalised + 权限 + 持币集中度）、
MCP 协议一致性（顶层 error / batch / 405 / CORS / 版本协商 / structuredContent / annotations）、
153 项测试 + CI、文档去除仓位建议。

**🔴 最高优先：准确率基准**

拿一批已知 rug + 已知正常代币跑一遍，公布**召回率和误报率**。

理由不变（风控产品建立信任的唯一方式、当前没人做），但现在多了一条更硬的：
**我们刚证明了自己有能力在"看起来正常"的情况下让一整个检测维度静默失效半年。**
没有基准，下一次这种事仍然只能靠偶然发现。基准就是这个产品的回归测试。

落地方式建议（按可行性排序）：
1. 正样本：honeypot.is 判 `very_high` + RugCheck `rugged=true` 的历史代币
2. 负样本：CoinGecko 市值前 500 且有 DEX 池的代币
3. 指标：召回率（漏报致命风险的比例）、误报率（把正常币判 high 的比例）、
   以及 **unknown 率**——这个数字诚实与否，直接决定产品可不可信
4. 结果写进 README 并随每次发布更新

**🟡 已知缺口（按 rug 预防价值/工程量排序）**

| 缺口 | 说明 |
|---|---|
| EVM 侧持币集中度 | Solana 侧已经有了（RugCheck topHolders），EVM 侧缺。需要 GoPlus `token_security`（免费、免 key），同时能一并拿到 mint/blacklist/可改税权限、LP 锁仓 |
| LP 锁仓/销毁 | 撤池是 EVM 侧最主要的 rug 形态，目前完全没覆盖 |
| 同名代币冲突检测 | agent 场景最常见的损失不是买到 honeypot，是**买到假的那个**。数据源已有（DexScreener 搜索），未做 |
| 缓存 | 每次调用打 2-4 个上游，无缓存。热门币加 30-60s TTL 可显著降延迟与被限流风险 |
| 限流/滥用防护 | 公开无鉴权端点，无任何速率限制 |
| 可观测性 | 无日志、无指标，线上出问题只能靠人工复现 |

**🔵 需要 Jake 拍板的事**（见第 7 节）：见下方"待决事项"。

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

---

## 9. 待决事项（需要 Jake 拍板）

1. **是否 push + 部署本轮修复。** 分支 `fix/p0-honeypot-liquidity`，本地已提交，
   153 项测试全绿。线上当前跑的仍是 honeypot 检测失效的版本。

2. **公开仓库里的基础设施标识。** 第 2 节表格里的 Cloudflare Account ID
   (`3976e6f6...`) 和 Zone ID (`371490a6...`) 提交在**公开仓库**里。
   这两个不是密钥、单独拿到无法操作账号，但它们是攻击者做定向社工/钓鱼时的有效信息。
   建议移到私有笔记，repo 里只留一句"向 Jake 索取"。已确认 git 历史中**没有**
   提交过任何 token/凭证文件。

3. **落地页语言。** 目前纯中文。这个工具本身没有语言属性，
   中文页面直接切掉了绝大部分潜在用户。建议做英文版（或双语）。

4. **分发。** 官方 MCP registry 尚未注册（`docs/server.json` 已就绪但没提交上去）。
   awesome-mcp-servers、Smithery、mcp.so、PulseMCP、Glama 均未收录。
   这几件都是一次性投入、长期获客。

## 10. 给下一个接手者的三条

1. **先跑测试再改代码。** `python tests/test_risk.py` 应当 71/71。
   如果它红了，说明有人改坏了某条曾经真实发生过的缺陷路径。

2. **上游契约测试红了，不一定是你的错。** 它连真实 API，第三方改字段就会红。
   红了先看是不是上游变了，然后同步改 `risk.py`——这正是它存在的意义。

3. **fail-closed 是这个产品唯一不能妥协的东西。** 任何时候你要写
   "拿不到数据就默认 X"，停下来。正确答案永远是 `unknown` + 记进 `data_gaps`。
   一个诚实说"我不知道"的风控工具有价值；一个猜错的没有。

---

## 11. 分发：已完成 / 待你操作

### ✅ 已完成（2026-09-04）

| 渠道 | 状态 | 备注 |
|---|---|---|
| **官方 MCP Registry** | 已上线 `dev.vetagent/vetagent` v0.2.0 | 用**域名验证**而非 GitHub 账号，命名空间挂在产品域名上，不挂在个人账号上 |
| **PulseMCP** | 自动 | 它从官方 registry 抓取，无需单独提交 |

**重新发布的方法**（版本号变更时）：

```bash
# 私钥在 C:\Users\86277\.vetagent-secrets\key.pem —— 仓库外，绝不提交
PRIV="$(openssl pkey -in ~/.vetagent-secrets/key.pem -noout -text | grep -A3 'priv:' | tail -n +2 | tr -d ' :\n')"
mcp-publisher login http --domain vetagent.dev --private-key "$PRIV"
cd docs && mcp-publisher publish
```

公钥由 Worker 在 `/.well-known/mcp-registry-auth` 提供（见 `src/entry.py`）。
**私钥丢了就换不了命名空间下的版本**，建议同时存进密码管理器，
以及作为 GitHub Secret（`MCP_REGISTRY_KEY`）供 CI 自动发布。

### ⬜ 需要 Jake 本人操作（都要注册账号，我无法代劳）

| 渠道 | 入口 | 需要什么 |
|---|---|---|
| **Claude 插件目录** | https://platform.claude.com/plugins/submit | 注册 Console（免费，注册即为 Owner），填仓库地址 `github.com/jakegu1/vetagent`。仓库侧前置已全部就绪：`.claude-plugin/plugin.json`、`.mcp.json`、LICENSE、公开仓库 |
| **Glama** | https://glama.ai/mcp/servers | GitHub OAuth，需对本仓库有写权限 |
| **Smithery** | https://smithery.ai/new | Smithery 账号 + API key（拿到 key 后可以命令行发布） |
| **mcp.so** | https://mcp.so/submit?type=remote-server | 站内邮箱密码账号（注意：**该站关闭了密码重置**，务必存进密码管理器） |
| **awesome-mcp-servers** | https://github.com/punkpeye/awesome-mcp-servers | GitHub PR。⚠️ 该仓库的机器人要求先有 **Glama 收录**才给过检查，所以顺序是先 Glama 再提 PR |

> 提交文案统一口径：**只读分析工具，不执行交易、不提供投资建议**。
> 这不只是合规措辞——它就是产品的真实边界，也是 §5 禁止返佣那条的同一个理由。
