# 决策记录 (DECISIONS.md)

> 这不是流水账。**每条决策只占一行**，除非它当初的代价值得写长。

## 这个文件怎么用

**收录标准（只有一条）**：*不知道这件事的人会不会踩坑？*
会 → 收录。不会 → 它属于 commit message，不属于这里。

**为什么不把「为什么」全写进文档**：因为文档会烂，而且烂得无声无息。
所以每条决策都必须回答「**由什么在强制它**」：

| 强制方式 | 含义 |
|---|---|
| 测试名 | 违反会让 CI 变红。**最强**——规则自己会报警 |
| CI | 由 workflow 保证 |
| 运行时 | 代码里的断言，违反直接失败 |
| 无 | 只是写着。人可以忽略。**这是待办，不是终点** |

> **本文件的目标是让「无」这一列逐渐消失。**
> 一条重要决策如果还停在「无」，说明我们还没真正落实它，只是记下了它。

**淘汰规则**：状态改成 `已推翻` 的条目压缩成一行，指向取代它的条目，不保留原文。
表格超过 40 行时，把所有「由测试强制」且从未失败过的条目合并成一行摘要——
它们已经不需要文字了，测试就是文档。

**不属于这里**：某段代码为什么这么写（→ 写在代码注释里，就在那段代码旁边）、
某次改动为什么做（→ commit message，它不可篡改且贴着 diff）、
当前进度和待办（→ HANDOFF.md）、生意判断（→ STRATEGY.md）。

---

## 决策表

| # | 决策 | 为什么 | 由什么强制 | 状态 |
|---|---|---|---|---|
| **风控引擎** |
| E1 | honeypot 标志读 `honeypotResult.isHoneypot` | 上游 `simulationResult` 里没有这个键，读它恒为 False → 对所有代币输出"安全" | `test_honeypot_key_is_read_from_the_right_object` + `test_honeypot_is` | 生效 |
| E2 | 仿真失败 → `critical` 而非放行 | 「买不进去」被当成「没问题」是最危险的误判 | `test_simulation_failure_is_fail_closed` | 生效 |
| E3 | `_fetch_json` 失败返回 `None`，不返回 `{}` | 调用方必须能区分「抓取失败」和「确实没内容」，这是 fail-closed 的前提 | `test_upstream_failure_yields_unknown` | 生效 |
| E4 | 关键维度缺数据 → `unknown` | 风控工具猜错比说不知道更糟 | `test_upstream_failure_yields_unknown` | 生效 |
| E5 | 评分＝最坏信号主导 + 封顶佐证加成，不是求和 | 求和模型下"信号越多分越高"，加几个维度就会把正常币推成 high | `test_clean_token_stays_low` | 生效 |
| E6 | `confidence` 衡量数据完整度，不是风险高低 | 原实现反了：数据越全反而 confidence 越低 | `test_upstream_failure_yields_unknown` | 生效 |
| E7 | 无 `chain_hint` 时按链的规范性收敛，不按中位价 | pulsechain 等分叉链继承合约地址；USDC 的 30 个池有 29 个在那儿，按数量投票必然被带偏 | `test_liquidity_picks_the_right_pool` | 生效 |
| E8 | `pairCreatedAt` 按毫秒整数解析 | 上游给的是 int，旧代码调 `.replace()` 抛错后被吞，年龄信号从未生效 | `test_pair_age_works_on_integer_timestamps` + `test_dexscreener` | 生效 |
| E9 | Solana 用 `score_normalised`，并读 mint/freeze 权限与持币集中度 | 原用 raw score 比阈值 5000——BONK 的 raw score 是 101，任何币都无条件通过 | `test_solana_rugcheck_signals` | 生效 |
| E10 | `evidence` 默认精简，`verbose` 才全量 | MCP 场景里 token 就是钱 | `test_output_is_compact` | 生效 |
| **MCP 协议** |
| M1 | JSON-RPC 错误放顶层，不塞进 `result` | 合规客户端会把 `result.error` 读成成功 | `test_errors_are_top_level` | 生效 |
| M2 | 手写 MCP 端点，不用官方 SDK | 官方包依赖 pydantic 的 C 扩展，Pyodide 装不上（实测） | 无 | 生效 |
| M3 | 工具接口全英文 + 必须有 `title` | 描述是调用方模型**唯一**的使用说明；中文直接卡住海外采用 | `test_tools_list_shape` | 生效 |
| M4 | 描述里必须写明 `unknown` ≠ 低风险 | 模型不理解 unknown 时会当成 low 处理，这是最危险的误读 | `test_tools_list_shape` | 生效 |
| **部署与运维** |
| D1 | 一律 `pywrangler deploy`，禁用裸 `wrangler` | 后者构建成功、dry-run 也过，但线上启动即 `ModuleNotFoundError`——它不 vendor workers-py | CI (`deploy.yml`) | 生效 |
| D2 | 部署跑在 CI，不跑在个人电脑 | Windows 上 pywrangler 跑不起来；上线能力不能绑在某台机器上 | CI (`deploy.yml`) | 生效 |
| D3 | 部署后必须对线上冒烟测试 | 「部署成功但产品是坏的」这个项目已经经历过一次 | CI (`deploy.yml`) | 生效 |
| D4 | MCP Registry 用**域名验证**，不用 GitHub 账号 | `io.github.<某人>/` 把产品身份绑在个人账号上，而命名空间事后改不了只能弃用重来 | 无 | 生效 |
| D5 | 采用 MIT 许可 | 落地页早已声称 MIT；让声明变成真的。插件分发也要求开源 | 无 | 生效 |
| **基准** |
| B1 | 标注器端点与引擎端点**不得相交** | 否则测的是「引擎能不能转述上游」，必然高分且无意义 | 运行时（`run_benchmark.py` 相交即退出非零） | 生效 |
| B2 | GoPlus 刻意不接进引擎 | 它是基准的留出预言机；接进去基准立刻失效 | `test_benchmark_oracle_stays_out_of_the_engine` | 生效 |
| B3 | 必须同时报消融列 | 已死的池子流动性≈0，靠这条判 high 接近同义反复 | 无 | 生效 |
| B4 | `unknown` 率必须与召回率并列 | 对所有东西答 unknown 的工具召回率完美、价值为零 | 无 | 生效 |
| B5 | 合约特权函数 ≠ 危险 | 见下方 L1 | 无 | 生效 |
| B6 | 排除 `hidden_owner` 和 `honeypot_with_same_creator` | 见下方 L2 | 无 | 生效 |
| B7 | 对高声誉资产加护栏，宁可不标注 | 见下方 L3 | 无 | 生效 |
| **产品与生意** |
| P1 | **不接返佣 / 订单流分成 / 项目方付费评级** | 唯一的资产是"说这个币危险时没人怀疑我们的动机"。收入一旦与"判 low"相关，资产瞬间归零且不可恢复 | 无 | 生效 |
| P2 | 主攻交易机器人运营方，不是个人用户 | 有收入、有赔付责任的人才会付钱 | 无 | 生效 |
| P3 | 决定不再维护时**必须主动下线** | 无人维护的风控工具会继续自信地输出错答案，是负债不是资产 | 无 | 生效 |
| P4 | 每天采集新池快照 | 公开源只列活着的池子（实测 199 个样本采到 0 个 dead）；这份数据买不到也补不回来 | 无 | 生效 |

---

## 代价高的四次翻车

只有这几条值得写长——**因为它们都是"看起来完全正常"的错误**，
而这正是这个产品最容易死的方式。

### L1 · 把"合约有特权函数"当成危险

第一版基准标注器把可暂停、有黑名单、可增发判为 unsafe，
结果 **USDT、WBTC、LDO 全被标成诈骗**。

这些特权是中心化资产的设计，不是 rug。照那个标准去评分，
等于**逼着引擎把蓝筹判高危**——一个基准如果校准错了，它会主动把产品带向错误方向。
**校准错的基准比没有基准更有害。**

→ 拆成独立的 `centralized` 档，不计好坏，只用来观察引擎会不会无差别打高危。

### L2 · 用株连型字段当证据

修完第一版还是错。`hidden_owner`（在合法可升级代理上误触）和
`honeypot_with_same_creator`（"部署者部署过被标记的合约"）
又把 **AAVE、YFI、PAXG、SNT、Base 上的 USDT** 标成危险。

第二个字段的问题最典型：大发行方和部署工厂会部署上千个合约，难免混进骗局。
**那是株连，不是这个代币本身的性质。**

### L3 · 以为可以用一个风控工具给另一个打分

**GoPlus 把真的 Status(SNT) 标成 `is_honeypot: 1`。**
连"确定性"字段都有误报。

→ 推论：**用风控工具当 ground truth，天花板就是它自己的精度。**
唯一的真实基准是"后来实际发生了什么"。高声誉资产出现对抗标记时排除而非错标。

### L4 · 以为召回率可以直接测出来

想测"已 rug 的代币能不能拦下"，**199 个样本采到 0 个 dead**。

不是采样写得差——DexScreener 搜索和 GeckoTerminal 列表都按流动性排序，
**死掉的池子直接从列表消失**。幸存者偏差，用钱和算力都绕不开，
那份数据在公开接口上根本不存在。

→ 这条同时证明了两件事：基准在"拦截 rug"维度上**暂时不可测**（诚实标注，不伪造数字），
以及 **P4 的快照库是唯一出路**，而且每拖一天就永久少一天。

---

## 待办：把「无」变成「有」

下面几条现在只靠人记着，应当变成能自己报警的东西。按价值排序：

1. ~~**B2**（GoPlus 不得进引擎）~~ → **已完成 2026-09-04**。
   `test_benchmark_oracle_stays_out_of_the_engine` 扫 `src/`，出现即变红，
   并已反向验证过它确实会失败——不会失败的守卫测试等于没有。
2. **B3 / B4**（消融列、unknown 率必须报告）→ 让 `run_benchmark.py` 在缺这两项时退出非零。
3. **P4**（每日快照）→ 加 GitHub Actions 定时任务，断更即告警。
   现在靠手动跑，而它的全部价值就在于不断更。
4. **D4 / D5**（域名命名空间、MIT）→ 一次性决策，不需要强制，保持「无」即可。

---

*每条决策都能在 `git log` 里找到对应 commit，那里有完整的推理过程。
这份表只回答「是什么、为什么、谁在守着」，不复述过程。*
