# ok-chaos 开发交接

## 基线概况

- 快照日期：2026-07-17
- 仓库位置：`E:\github\ok-chaos`
- 分支：`main`
- 版本：`0.1.0`
- 运行环境：Windows 11、Python 3.12
- 框架：`ok-script==1.0.163`
- 当前仓库没有配置 Git remote；本次是该仓库的首个提交基线。

这是一个基于 ok-script 的全新卡厄思自动化项目。`ok-kes` 只作为行为和页面资料参考，项目没有复制它的
处理器链。当前重点是先建立可信的角色牌数据、采集、识别和运行时准入闭环，再接战斗策略。

范围只包含角色专属卡牌及其普通闪、专属灵光一闪、神闪和角色强化。中立牌、怪物牌不建立定义。

## 当前已经完成

### 框架与安全边界

- `src/tasks/ChaosTask.py` 是唯一调用 ok-script API 的模块。
- `src/chaos/` 是可脱离 GUI 和游戏运行的纯识别、状态与决策核心。
- 主任务每轮只读取一份 OCR 上下文、只做一次页面决策、最多执行一个动作。
- 所有页面处理器同时评分；低置信度或歧义页面不点击。
- 相同画面和动作有冷却保护，删除存档等破坏性操作只识别、不执行。
- 未知页面默认无操作；采集与实时卡牌识别均走只读旁路。

### 卡牌数据与采集

- 已实现 `CardDefinition`、`CardVariant`、`EffectSpec`、`MaterializedCard` 和严格的 `CardCatalog`。
- 已实现一帧、一次 OCR、零动作的被动采集器。
- 已实现经过列表页和详情页验证的海德玛丽基础详情、灵光一闪总览采集任务。
- 已实现灵光一闪五分支切分工具；切分结果仍是 `pending`，不会自动进入正式目录。
- 所有采样默认保留在本地并经过右下角隐私遮挡。

### 闪光识别

- 当前试点角色是 `haide_mali`（海德玛丽/海德瑪麗）。
- 可识别四张候选角色牌的卡名、普通闪、专属灵光一闪和神闪。
- 使用简繁归一、保留数字的文字匹配，并在普通闪/神闪文字冲突时检测左侧金色神闪徽记。
- 普通闪与专属灵光一闪处于互斥基础层；神闪是可叠加的独立层。
- 灵光一闪分支的效果文本可能与基础卡面完全一致（如万人的英雄分支 a 仅新增 `[連結]` 特性标签）。此类分支在
  `epiphany.pending.json` 中标注 `required_trait_tags_zh_tw`，识别时必须额外看到括号形式的特性标签才会判定。
- 实时任务只 OCR 卡牌详情相关区域，完整内存帧仅用于位置和金色徽记判断，不保存 `frame.png`。

### RuntimeCardIndex 与 CardObservation

当前实时链路是：

```text
CurrentCardRecognitionTask
  → 一帧局部 OCR
  → ScreenContext
  → RuntimeCardIndex.recognize_flash()
  → FlashRecognition
  → CardObservation
  → RuntimeCardIndex.resolve()
  → READY + MaterializedCard，或明确拒绝进入策略层
```

`RuntimeCardIndex` 在任务首次运行时预编译只读表，并在后续运行中复用：

- 4 张候选牌，0 张已审核牌；
- 11 个卡名键；
- 45 个候选效果、79 个效果文字键；
- 155 个候选变体，0 个已审核变体。

`CardObservation` 保存本帧卡牌实例、身份、组合变体、画面区域、运行时状态和分字段置信度。候选资料可以
帮助识别，但不能直接驱动策略。只有基础牌和全部活动变体都存在于 `data/cards`，并且目录层级组合校验通过，
`RuntimeCardResolution.decision_ready` 才会为 `true`。

当前正式目录只有角色壳，卡牌和变体均为空。因此真实样本的预期结果是“识别成功、策略不可用”。这是安全
门槛生效，不是识别失败。

## 数据权威等级

从高到低依次为：

1. `data/cards/characters/*.json`：人工审核后的正式事实，策略层唯一权威来源。
2. `datasets/cards/review/**/*.pending.json`：从实机样本整理出的待审核结构化摘要，只参与识别。
3. `datasets/cards/reference/**/*.pending.json`：网页与历史资料候选，只参与识别和规划采集目标。
4. `datasets/cards/inbox/`：本地原始采集证据，不得自动提升为正式数据。

仓库特意跟踪两份结构化 `review/*.pending.json`，因为运行时与测试依赖它们。`inbox` 默认仍被忽略；例外是两个
经过隐私遮挡的回归夹具，CI 用它们验证真实画面识别，且都保持 `pending`，不能据此自动批准正式卡牌定义：

- `s20260717-114847-312497-2076b1a9`：剑之雨普通闪正样本（局内画面）。
- `s20260717-165108-416089-0041bee0`：万人的英雄基础详情负样本（局外画面）。其效果文本与灵光一闪分支 a
  完全相同，用于锁定“文本无差异的分支必须看到 `[連結]` 特性标签才能判定”的行为。

## ok-script 任务

| 任务 | 类型 | 当前行为 |
| --- | --- | --- |
| `ChaosTask` | 持续触发 | 基础页面状态机；默认关闭，每轮最多一个动作 |
| `CurrentCardRecognitionTask` | 一次性 | 只读识别当前详情页并显示观察与策略准入结果 |
| `CardCollectorTask` | 一次性 | 保存一帧脱敏画面、同帧 OCR 和 pending 清单 |
| `AutoCardCollectorTask` | 一次性 | 在已验证列表/详情循环中逐卡位采集基础详情；右下角有灵光一闪按钮时进入总览一并采集后返回 |

任务注册位于 `src/config.py`。不要把 ok-script 调用移动进 `src/chaos/`。

## 关键文件

- `src/tasks/ChaosTask.py`：ok-script 任务适配、一次性采集与实时识别入口。
- `src/chaos/cards/runtime_index.py`：运行时只读索引、观察转换和审核目录准入。
- `src/chaos/cards/flash_recognizer.py`：卡名、效果层和神闪徽记识别。
- `src/chaos/cards/schema.py`：角色牌、变体、实体牌与观察对象模型。
- `src/chaos/cards/catalog.py`：正式目录加载、关系校验和变体实体化。
- `datasets/cards/reference/haide_mali/flash_layers.pending.json`：普通闪与神闪候选词库及识别布局。
- `datasets/cards/review/haide_mali/epiphany.pending.json`：20 个实机灵光一闪分支摘要。
- `datasets/cards/review/haide_mali/common_flash.pending.json`：已确认画面种类的剑之雨普通闪摘要。
- `data/cards/characters/haide_mali.json`：正式目录入口；当前 `cards=[]`、`variants=[]`。
- `docs/CARD_SYSTEM.md`：卡牌系统、采集和识别使用说明。
- `docs/ARCHITECTURE.md`：框架边界和单轮运行不变量。

## 开发与验证命令

```powershell
.\scripts\setup.ps1
.\scripts\test.ps1
.\scripts\run-debug.ps1
.\scripts\run.ps1
.\scripts\build.ps1
```

卡牌数据工具：

```powershell
.\scripts\cards.ps1 validate-catalog
.\scripts\cards.ps1 validate-samples
.\scripts\cards.ps1 split-epiphany
.\scripts\cards.ps1 recognize-flash <manifest.json> --ignore-label
```

本基线最后一次完整校验结果：

- Ruff：通过；
- pytest：67 个测试全部通过；
- 正式目录：1 个角色、0 张基础牌、0 个变体、1 个数据文件；
- 本地样本：41 份清单校验通过；
- PyInstaller 单文件构建：成功。

本地构建产物为：

```text
dist/ok-chaos-win32-portable-v0.1.0.exe
大小：177466855 bytes
SHA-256：3954C514E8E612471EF400D32571510D4416C60CD7C33B1F0EB26C4255F9C70A
```

`dist/`、`build/` 和 `.spec` 均被忽略，不属于 Git 提交。构建脚本已经显式打包 `data/cards`、普通/神闪
候选 JSON 和灵光一闪候选 JSON。重建前需要关闭正在运行的管理员权限 EXE，否则 Windows 会锁定目标文件。

## 已知限制

- 只完成海德玛丽试点，且只覆盖当前四张可闪角色牌的详情页闪光识别。
- 正式卡牌目录仍为空，尚无任何观察能够进入策略层。
- 普通闪与神闪候选不完整，并且包含网页来源与版本冲突，必须继续保持 pending。
- 尚未识别详情页费用、类型图标或卡图感知哈希。
- 尚未实现战斗手牌定位、跨帧实例跟踪、动态费用、选中态、可用态和出牌策略。
- `CardObservation.runtime_states` 和 `current_cost` 当前为空，字段已预留。
- 识别器依赖 OCR 文字和局部视觉证据，不需要把整张 `frame.png` 放进运行时资产库。
- STOVE 游戏以管理员权限运行时，ok-chaos 也必须管理员启动才能注入鼠标；WGC 捕获本身可以正常工作。

## 已入库的正式目录

`data/cards/characters/haide_mali.json` 已写入 7 张基础牌 + 21 个变体，经 2026-07-18 人工审核，
覆盖身份、类别、费用、目标、特性标签和效果原文：

- 7 张基础牌（card_01–card_07）。
- 20 个专属灵光一闪分支（card_03–card_06 各 a–e，`kind=epiphany`）；epiphany 用 `effects_override`
  整体替换基础效果，费用/类型/特性差异分别用 `cost_override`/`card_type_override`/`tags_add`/`tags_remove`。
  card_06 分支 e 是“改变类型的灵光一闪”，仍为 `kind=epiphany` 但 `card_type_override=upgrade`。
- 1 个剑之雨普通闪 `common_flash_draw_1`（`kind=common_flash`，叠加 `additional_effects`）。剑之雨普通闪
  的其余 5 个候选仅有网页文本、无实机证据，保持 pending，未入库。
- `effects`/`effects_override`/`additional_effects` 仍是占位：单个 `unsupported` 动作携带效果原文，
  `trigger` 为占位值，机器可读的效果 DSL 留待下一轮。不要把 `trigger`/`actions` 当作已确认事实。
- `card_07`（凝结极光）不可直接打出，`base_cost` 使用 sentinel `-1`（见 `schema.UNPLAYABLE_COST`），
  区别于 `null`（动态费用）；`target` 记为 `none`。
- 特性标签用英文键：`link`（連結）、`rest`（安息）、`unique`（唯一）、`quick`（快速）、`exhaust`/`exhaust_2`
  （消滅）、`ultimate`（終極）、`retain`（保留）、`reclaim_3`（回收3）。

**READY 真机路径已打通**：剑之雨普通闪的实机样本经"识别 → CardObservation → RuntimeCardResolution"
产出 `READY` 与可用的 `MaterializedCard`（`decision_ready=true`），由
`test_real_sword_rain_sample_reaches_strategy_ready_through_approved_catalog` 固定。基础牌页面仍正确返回
"识别成功、策略不可用"（无闪光层）。

### 待办：角色衍生牌

`极光劍`（極光劍/aurora_sword）和 `解放极光`（解放極光）是海德玛丽的战斗内生成牌，详情页 OCR 已多次
出现（如剑光/剑之雨/展开极光左侧的极光剑预览、凝结极光的解放极光形态），但没有干净的独立详情帧。
按约定改到**战斗内采集**：等实战采到它们的详情画面再建立正式 `CardDefinition`，不要用碎片 OCR 硬造。

## 推荐的下一步

1. 补齐基础牌与变体的效果 DSL（`trigger`/机器可读 `actions`），替换当前的 `unsupported` 占位。这是让策略
   真正能用 `MaterializedCard` 的前提。
2. 补充剑之雨普通闪其余候选与其他三张牌的普通闪：需要实机样本佐证后才入库，网页文本候选保持 pending。
3. 战斗内采集角色衍生牌（极光剑、解放极光）并入库。
4. 扩展详情页观察：费用数字、类型图标、卡图感知哈希和更多拒识负样本。
5. 再做战斗手牌定位与跨帧 `CardObservation` 跟踪。
6. 最后才让策略读取 `decision_ready=true` 的 `MaterializedCard` 并产生动作。

## 接手时的快速检查

```powershell
git status --short
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\scripts\cards.ps1 validate-catalog
```

真机检查在局外即可完成：在角色卡牌列表打开任意词库内卡牌（card_03/04/05/06）的基础详情，运行“识别当前
卡牌闪光（只读）”。应看到：卡名与 card_id 识别成功、闪光层为空（基础牌的正确结果）、“策略可用”为“否”；
词库外卡牌（card_01/02/07）应返回“未识别”而不是猜测身份。普通闪等局内画面的识别由两个入库夹具的离线
回归覆盖（`recognize-flash` + CI），不要求真机触发。整个过程不得点击游戏或保存截图。

继续开发前先阅读根目录 `AGENTS.md`。尤其不要自动批准 OCR 结果、不要建立中立/怪物牌定义，也不要在未知
或歧义页面上增加点击。
