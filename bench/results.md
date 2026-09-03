# VetAgent 准确率基准

> 本文件由 `python bench/run_benchmark.py` 生成，不要手改。

样本量 **205**。这是 v1，样本偏小，请把它当作「有没有明显失效」的体检，而不是精确的统计结论。


## 方法

标注**不使用引擎读取的任何端点**，否则测的是「引擎能不能转述上游」。


| | 标注依据 | 引擎是否读取 |
|---|---|---|
| `outcome` | GeckoTerminal 日线 OHLCV 历史（价格 + 成交量） | 否，引擎只看当前快照 |
| `goplus` | GoPlus token_security | 否，刻意保留作标注器 |

**运行时断言**：引擎访问端点 ∩ 标注器访问端点 = ∅，不满足时基准直接判定失效并退出非零。本次运行结果：**通过**。


<details><summary>本次实际访问的端点</summary>


引擎：

- `api.dexscreener.com/latest/dex/tokens/{id}`
- `api.honeypot.is/v2/IsHoneypot`

标注器：


</details>


### 标签定义

- **dead**：曾有真实成交（峰值 7 日量 ≥ $50k），后价格自峰值回撤 ≥ 90% **且**近 7 日量塌到峰值 5% 以下。只跌不算死，只是没量也不算死。

- **alive**：≥ 90 天历史，回撤 ≤ 70%，近 7 日量 ≥ 峰值的 10% 且 ≥ $50k。

- **unsafe**：GoPlus 命中 honeypot / 可暂停 / 黑名单 / 税率可改 / 可收回所有权 / owner 可改余额 / 可增发且 owner 未放弃 / 买卖税 >10%。

- **safe**：以上全不命中，且开源、持有者 ≥ 100。


中间地带一律不标注——宁可样本少，不要标签脏。


## 总体

| 指标 | 值 |
|---|---|
| 判定分布 | high=32, low=102, medium=28, unknown=43 |
| unknown 率 | 21.0% |
| 存在数据缺口的比例 | 25.4% |

> unknown 率必须和召回率一起看。一个对所有东西都答 unknown 的工具召回率完美，但毫无用处。


## 结果论标注（已死 vs 存活）


### 完整信号


| | n | 判 high | 判 high 或 medium | 判 low | 判 unknown | 平均分 |
|---|---|---|---|---|---|---|
| **已死** | 1 | 0.0% | 100.0% | 0.0% | 0.0% | 24.0 |
| **存活** | 97 | 11.3% | 19.6% | 66.0% | 14.4% | 17.4 |

### 仅合约安全类信号（消融）

剔除流动性/活跃度/新鲜度/跨链后重算。这一栏才是引擎在「显而易见的事情」之外的真实判断力。


| | n | 判 high | 判 high 或 medium | 判 low | 判 unknown | 平均分 |
|---|---|---|---|---|---|---|
| **已死** | 1 | 0.0% | 0.0% | 100.0% | 0.0% | 0.0 |
| **存活** | 97 | 9.3% | 25.8% | 74.2% | 0.0% | 15.8 |

**已死样本上，是哪类信号做出的判定：** `liquidity` 1


> 若这里高度集中在 `upstream_risk`，说明引擎主要在转述 honeypot.is，自身增量有限。


## GoPlus 留出预言机（危险 vs 安全）


### 完整信号


| | n | 判 high | 判 high 或 medium | 判 low | 判 unknown | 平均分 |
|---|---|---|---|---|---|---|
| **危险** | 1 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0 |
| **安全** | 140 | 16.4% | 27.9% | 50.0% | 22.1% | 26.3 |

### 仅合约安全类信号（消融）

剔除流动性/活跃度/新鲜度/跨链后重算。这一栏才是引擎在「显而易见的事情」之外的真实判断力。


| | n | 判 high | 判 high 或 medium | 判 low | 判 unknown | 平均分 |
|---|---|---|---|---|---|---|
| **危险** | 1 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0 |
| **安全** | 140 | 12.9% | 38.6% | 61.4% | 0.0% | 22.7 |

**危险样本上，是哪类信号做出的判定：** `honeypot` 1


> 若这里高度集中在 `upstream_risk`，说明引擎主要在转述 honeypot.is，自身增量有限。


## 中心化资产对照组（不计好坏）

有特权函数（可暂停/黑名单/可增发）但**无对抗特征**的代币，USDT、WBTC、LDO 都属于此类。这些特权是中心化资产的设计，不是 rug。


这一档只用来回答一个问题：**引擎会不会把它们无差别打成高危。**大量判 high 说明阈值太钝，会在真实使用里制造刺耳的误报。


| 样本数 | 判 high 比例 | 判定分布 |
|---|---|---|
| 52 | 11.5% | high=6, low=27, medium=10, unknown=9 |

样例：CP(unknown)、VIRTUAL(low)、BIO(low)、MOCA(low)、align(high)、umia(medium)、SOSO(low)、AAVE(low)、AVNT(low)、ZEST(unknown)


## 分歧样本（需人工复核）

标注和引擎判断不一致的样本。**漏报**（标注说危险、引擎说 low）优先看，每一条都可能是一个真实缺陷；**误报**（标注说安全、引擎说 high）同样要看，误报会直接摧毁用户信任。


| 类型 | 代币 | 链 | 标注 | 引擎判定 | 消融后 | 驱动信号 |
|---|---|---|---|---|---|---|
| 误报 | `O` | base | goplus=safe | high | high | honeypot |
| 误报 | `RECALL` | base | outcome=alive | high | high | sellability |
| 误报 | `RECALL` | base | goplus=safe | high | high | sellability |
| 误报 | `QWLA` | base | outcome=alive | high | high | honeypot |
| 误报 | `RIZE` | base | goplus=safe | high | medium | sellability |
| 误报 | `GOOGLc` | base | goplus=safe | high | high | honeypot |
| 误报 | `Basecat` | base | goplus=safe | high | high | honeypot |
| 误报 | `NVDAc` | base | goplus=safe | high | high | honeypot |
| 误报 | `VCNT` | base | outcome=alive | high | high | sellability |
| 误报 | `VCNT` | base | goplus=safe | high | high | sellability |
| 误报 | `ASTER` | bsc | outcome=alive | high | high | honeypot |
| 误报 | `ASTER` | bsc | goplus=safe | high | high | honeypot |
| 误报 | `AKE` | bsc | outcome=alive | high | high | honeypot |
| 误报 | `UAI` | bsc | outcome=alive | high | medium | sellability |
| 误报 | `UAI` | bsc | goplus=safe | high | medium | sellability |
| 误报 | `COLLECT` | bsc | goplus=safe | high | medium | sellability |
| 误报 | `quq` | bsc | goplus=safe | high | high | honeypot |
| 误报 | `mubarak` | bsc | outcome=alive | high | high | honeypot |
| 误报 | `mubarak` | bsc | goplus=safe | high | high | honeypot |
| 误报 | `HEMI` | bsc | goplus=safe | high | high | honeypot |

（另有 14 条，见 `results.json`）


## 这份基准测不到什么

1. **测不到「事前预警」。** 引擎评估的是当前状态，而 `dead` 标签是事后的。一个已经死掉的池子现在流动性≈0，判 high 接近同义反复——消融那一栏就是为此存在的。要真正回答「买之前它会不会警告我」，需要按时间点回放历史状态，而上游安全 API 不提供历史查询。

2. **`dead` ≠ 诈骗。** 正经项目也会死。这个标签回答的是「现在还能不能安全退出」。

3. **GoPlus 与 honeypot.is 可能相关。** 两者都做买卖仿真，所以 `goplus` 一栏的成绩会偏高。`outcome` 一栏没有这个问题。

4. **样本偏差。** 头部样本来自各链池子排行（偏健康），长尾样本来自关键词搜索（偏垃圾），不是真实调用分布的无偏抽样。

