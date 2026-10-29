# 面向服务保障的能源社区智能体

[English](README.md) | **简体中文**

这是一个研究原型，用于模拟可再生能源社区，并研究代码生成智能体能否在满足参与者服务要求和配电网约束的前提下，协调建筑、光伏、电池、电动汽车（EV）及柔性负载。

> **项目状态：** 仓库包含可运行的 Python 仿真原型、实验工具和 React 地图式结果前端，但还不是完整的端到端虚拟电厂（VPP）产品。生产后端、市场结算、配置化故障注入以及能真正改变控制行为的智能体修复尚未完成。解释实验结果前请先阅读[当前限制](#当前限制)。

## 目录

- [研究问题](#研究问题)
- [系统架构](#系统架构)
- [仓库结构](#仓库结构)
- [实验情景](#实验情景)
- [指标与实验设计](#指标与实验设计)
- [安装与运行](#安装与运行)
- [React 前端](#react-前端)
- [测试与当前验证状态](#测试与当前验证状态)
- [当前限制](#当前限制)
- [后续路线](#后续路线)

## 研究问题

本项目关注的问题是：

> 基于物理仿真的代码智能体，能否可靠地构建、执行、诊断并修复可再生能源社区仿真，同时保证个体服务需求并遵守配电网约束？

因此，评估目标不只是社区总成本或总购电量，还包括每辆 EV 是否在离站前达到目标 SOC、建筑舒适度是否受到影响、能源资产如何被使用，以及耦合配电网是否可行。

## 系统架构

| 层次 | 职责 | 主要实现 |
|---|---|---|
| 社区仿真 | 建筑负荷、光伏、储能、EV、柔性负载、观测与动作 | CityLearn v3 adapter |
| 协调控制 | 规则控制、分层多智能体控制、社区进出口限制 | `src/controllers/`、`src/coordination/` |
| 电网仿真 | 将建筑功率映射到配电网，计算潮流、电压与线路负载 | pandapower adapter |
| 评估 | 能源、服务、电网、智能体及成员级指标，图表和报告 | `src/evaluation/` |
| 智能体流程 | 规划、生成代码、沙箱执行、验证、修复与报告 | `src/agents/` |
| 结果前端 | 浏览已保存运行、空间图层、资产和时间步 | `frontend/` 中的 React、TypeScript、MapLibre、deck.gl 和 Plotly |

当前联合仿真顺序为：读取 CityLearn 观测、由控制器提出并应用动作、将建筑功率交给 pandapower，再把电网诊断记录到仿真时间步中。当前电网诊断主要用于事后验证；尚未普遍验证“电网违规反馈控制器、重新调度、再确认违规消除”的闭环。

## 仓库结构

```text
.
├── configs/                 # Scenario A–E 情景 YAML
├── data/schemas/            # CityLearn schema 和情景数据
├── experiments/
│   ├── run_experiment.py    # 单次情景／控制器实验
│   ├── run_benchmark.py    # 情景／控制器／随机种子组合实验
│   └── ...                  # 已保存实验结果与统计摘要
├── frontend/                # React + TypeScript + Vite 前端
├── src/
│   ├── agents/              # Planner、Coder、Executor、Verifier、Repair、Reporter
│   ├── controllers/         # 规则控制、集中式启发式、多智能体控制
│   ├── coordination/       # 建筑／资源智能体与社区聚合器
│   ├── evaluation/          # 能源、服务、电网、公平性指标与图表
│   ├── schemas/             # Pydantic 情景、动作、诊断与报告模型
│   └── simulation/          # CityLearn、pandapower adapter 与联合仿真
├── tests/                   # Python 自动化测试
├── project brief.md         # 完整产品／研究需求与首个里程碑
└── notes.md                 # 研究与论文规划笔记
```

实验输出写入指定目录。除非有意制作可复现的发布材料，否则不要把大型轨迹文件或绘图产物提交到版本库。

## 实验情景

当前五个 YAML 情景均以五栋建筑的社区为基础，位于 `configs/`。

| 文件 | 计划研究内容 | 当前配置状态 |
|---|---|---|
| `scenario_a.yaml` | 基准社区：光伏、电池、EV、柔性负载和分时电价 | 基准实验配置 |
| `scenario_b.yaml` | 更高 EV 渗透率及早晚离站充电期限 | 已有情景配置，运行结果仍需验证 |
| `scenario_c.yaml` | 更高光伏渗透率、外送和电网约束 | 已有情景配置，运行结果仍需验证 |
| `scenario_d.yaml` | 社区本地能源共享与结算 | 声明了共享配置；市场执行与结算尚未端到端实现 |
| `scenario_e.yaml` | 光伏、电池、充电器、传感器和电网限制故障 | 声明了故障情景；运行时注入与恢复尚未端到端实现 |

## 指标与实验设计

评估代码定义了以下类别的指标：

- **能源与成本：** 总成本、电网购电／外送、峰值功率、负荷率、光伏发电／自用／弃电、电池吞吐量／循环估计及碳排放。
- **参与者服务：** EV 完成率和离站 SOC、舒适度违规度时、柔性负载完成率／延迟、需求响应交付及成员级结果。
- **电网可行性：** 潮流收敛、电压边界与违规、线路／变压器负载、社区购电／外送限制。
- **智能体执行：** 任务和仿真成功率、首次代码有效率、修复次数、运行时间与报告完整性。

`experiments/run_benchmark.py` 当前支持 `rule_based`、`multi_agent`、`centralized`、`mpc` 和 `rl` 控制器标签：`mpc` 为确定性滚动时域线性规划，`rl` 从 `experiments/rl_policy/<scenario>.json` 加载表格 Q-learning 策略，集中式实现仍是启发式控制器。Benchmark 脚本支持多个随机种子并计算统计量和 95% 置信区间，但小型 smoke run 不足以支撑论文结论。研究 brief 要求每种配置至少运行 3–5 次，并补充 MPC／RL 和智能体验证机制消融实验。

> **修复前的 benchmark 数字无效。** 在种子可复现性修复（PR #1）之前生成的 benchmark 结果未给所有随机源设定种子，无法复现，请勿引用。引用任何数字前，请用当前代码重新运行；复现性门禁见 `docs/reproducibility.md`。

## 安装与运行

### Python 仿真

使用 Python 3.10 或更新版本。在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

运行单次实验：

```powershell
python experiments/run_experiment.py `
  --config configs/scenario_a.yaml `
  --controller rule_based `
  --seed 42
```

`--controller` 支持 `rule_based`、`multi_agent` 和 `centralized`。可选参数包括 `--max-steps`、`--output-dir`、`--seed` 和 `--run-id`。

运行小型 benchmark 示例：

```powershell
python experiments/run_benchmark.py `
  --scenarios configs/scenario_a.yaml `
  --controllers rule_based multi_agent `
  --seeds 42 123 `
  --output experiments/benchmark_test
```

Benchmark 默认运行 A–E 全部情景、三个控制器标签和五个随机种子，完整运行会比 smoke test 耗时更久。`experiments/run_all.sh` 是 Bash 脚本；Windows 下请使用 Git Bash、WSL 或其他 Bash 环境。

### React 前端

需要 Node.js 和 npm。在仓库根目录运行：

```powershell
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run dev -- --host 127.0.0.1
```

打开 Vite 输出的地址，通常为 `http://127.0.0.1:3000/`。VS Code 也配置了 **Run Virtual Community Frontend** 任务。

构建并执行 TypeScript 检查：

```powershell
npm.cmd --prefix frontend run build
```

### 本地结果 API

Vite 开发服务器带有只读本地中间件，会扫描仓库 `results/` 中的 `result.json` 及同目录的 `trajectories.jsonl`，为前端提供运行摘要和轨迹。这只是开发便利功能，**不是生产后端**。前端 API client 还定义了情景、仿真、智能体、报告、比较和 WebSocket 接口，但仓库目前没有与之配套的 FastAPI 服务。连接独立服务时可设置 `VITE_API_BASE_URL` 和 `VITE_WS_BASE_URL`。

## React 前端

默认路由是社区画布，包含：

- 从已保存的实验结果中选择 run。
- 基于 MapLibre 的底图和 deck.gl 图层：建筑、光伏、电池、EV、馈线、变压器、违规、热图及能量流。
- 时间轴拖动、播放／暂停、逐步移动、重置和速度控制。
- 按选中资产显示的资产／电网检查器。
- Scenario Studio、Agent Workspace、报告和运行比较等路由。

当前地图坐标是示意值。读取到保存结果时，run 数据是真实实验数据，但一些可视化和工作流尚不完整：地图没有载入真实电网拓扑，部分设备状态是由观测／动作推导的，情景、智能体和报告操作还依赖仓库未提供的后端路由。

## 测试与当前验证状态

在仓库根目录运行测试：

```powershell
pytest -q tests
```

测试覆盖控制器协同、CityLearn adapter、pandapower adapter、指标、benchmark 监督器和智能体修复框架。**全套测试当前通过**，包括针对 CityLearn adapter 时间步约定与控制器动作接口的回归测试。

## 当前限制

- Vite 本地结果中间件不是生产 API／后端。
- CityLearn adapter 时间步约定已统一并有回归测试保护（整数 schema 字段、CSV 长度与 episode 步数对齐、3600/3600.0 秒步长处理）。
- 电网违规会被记录，但尚未证明完整的电网反馈与重新调度闭环。
- 情景 schema 中有 `energy_sharing` 和结算选项，但没有端到端市场撮合或结算流程；成员结算收益仍是占位值。
- Scenario E 声明了故障，但配置化故障注入与恢复尚未端到端实现。
- 当前修复流程尚不能作为可信的代码修复结果：部分补丁应用是占位实现，sandbox 快速验证通过不代表目标服务／电网违规已在完整实验中消除。
- React 地图使用示意坐标，尚未显示真实 pandapower 网络几何。
- 前端时间标签假设 15 分钟步长；必须与使用数据集原生步长的 run 对齐。
- Benchmark 尚缺 brief 要求的 MPC、RL、未验证智能体与已验证智能体对照。

## 后续路线

1. ✅ **已完成** — 修复 adapter 测试，统一数据、控制和显示的时间步／单位约定。
2. 建立闭环联合仿真，使电网诊断可以约束或触发重新调度，并验证违规是否消除。
3. 让智能体补丁真正改变控制器行为，并通过完整实验的服务／电网指标验证修复。
4. 把能源共享、结算和故障配置实现为可执行的仿真行为。
5. 将 React Scenario Studio、Agent Workspace 和报告连接到真实 API，并载入真实资产／电网元数据及每个 run 的时间步信息。
6. 运行完整 benchmark，加入可复现随机种子、适当基线和统计分析。

完整产品定义、首个里程碑验收标准和论文定位见 [`project brief.md`](project%20brief.md)。

## 许可证

项目元数据声明使用 MIT。重新分发前，请确认仓库许可证文件及第三方素材的授权条款。