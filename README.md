# ok-chaos

`ok-chaos` 是一个基于 `ok-script` 的全新卡厄思自动化项目。旧的 `ok-kes` 只作为行为和页面资料来源，
本项目不继承它的处理器链、全局变量和任务间耦合。

当前版本建立了可运行的框架骨架：

- 显式注册唯一的 `ChaosTask`，不依赖目录扫描顺序。
- 每轮只截图/OCR 一次，并只执行一个动作。
- 所有页面同时评分，低置信度或歧义页面不操作。
- 相同画面上的相同动作有冷却保护。
- `ok-script` 适配代码与可单元测试的决策核心分离。
- 默认保留存档、默认关闭任务，破坏性动作不会静默执行。
- 角色牌数据库、效果 DSL 和变体叠加模型已经建立；中立牌、怪物牌明确排除。
- 提供一次一帧的被动采集，以及经列表/详情双重校验的基础详情和灵光一闪总览采集任务；
  样本必须人工审核后才能进入数据库。
- 提供“识别当前卡牌闪光（只读）”一次性任务；直接使用内存画面和一次 OCR 输出普通闪、专属闪与神闪组合，
  再转换成标准 `CardObservation` 并经过审核目录准入；不点击游戏，也不保存截图。

## 开发环境

要求 Windows 和 Python 3.12：

```powershell
.\scripts\setup.ps1
.\scripts\test.ps1
.\scripts\run-debug.ps1
```

正常启动：

```powershell
.\scripts\run.ps1
```

构建单文件程序：

```powershell
.\scripts\build.ps1
```

校验角色牌数据库或本地采集样本：

```powershell
.\scripts\cards.ps1 validate-catalog
.\scripts\cards.ps1 validate-samples
.\scripts\cards.ps1 split-epiphany
.\scripts\cards.ps1 recognize-flash <manifest.json> --ignore-label
```

采集第一批角色牌的具体步骤见 `docs/CARD_SYSTEM.md`。
当前实现状态、关键约束和接手顺序见 `docs/HANDOFF.md`。

## 目录

```text
src/tasks/ChaosTask.py       ok-script 的任务适配层
src/chaos/                   与框架解耦的识别、状态和决策核心
src/chaos/cards/             角色牌模型、运行时索引、效果 DSL、目录与采集样本格式
src/chaos/handlers/          独立页面处理器
data/cards/                  已审核、可提交 Git 的角色牌事实数据
datasets/cards/              本地采集样本；实际图片默认忽略
tests/                       不连接游戏也能运行的决策测试
docs/ARCHITECTURE.md         架构和扩展规则
docs/CARD_SYSTEM.md          卡牌数据闭环和采集操作
assets/                      后续重新采集的模板素材
```

现阶段只实现了少量低风险页面，用来验证新架构。完整卡厄思流程将按真实截图逐页补齐，不能把当前
`0.1.0` 当作已经可无人值守通关的版本。
