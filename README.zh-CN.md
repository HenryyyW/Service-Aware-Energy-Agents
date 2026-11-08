# 面向服务保障的能源社区智能体

[English](README.md) | **简体中文**

这是一个研究原型，用于模拟可再生能源社区，并探究代码生成智能体能否在满足参与者服务需求并遵守配电网约束的前提下，协调建筑、光伏、电池、电动汽车（EV）和柔性负载。

> **项目状态：** 可运行的研究原型——包含 Python 仿真与实验工具、FastAPI 服务（`backend/`）以及带可切换视觉样式的 React 地图前端（`frontend/`）。已实现并有测试覆盖：定价机制（pool-TOU / LMP）、P2P 匹配、场景 E 的配置化故障注入，以及 plan → code → execute → verify → repair 智能体工作流。它**仍不是**生产级虚拟电厂（VPP）：API 是本地/开发服务，LMP 分支在拥堵情况下以回退为主，P2P 运行未调度。引用任何数字前请先阅读[当前限制](#当前限制)。

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
- [部署](#部署)
- [许可证](#许可证)

## 研究问题

本项目探究的问题是：

> 基于物理仿真的代码智能体，能否可靠地构建、执行、诊断并修复可再生能源社区仿真，同时保证个体服务需求并遵守配电网约束？

系统意在评估的不只是社区总成本或总购电量，还包括每辆 EV 是否在离站前达到目标荷电状态（SOC）、建筑是否保持在舒适度界限内、能源资产如何被使用，以及耦合配电网是否保持可行。

## 系统架构

| 层次 | 职责 | 主要实现 |
|---|---|---|
| 社区仿真 | 建筑负荷、光伏、储能、EV、柔性负载、观测与动作 | CityLearn v3 adapter |
| 协调控制 | 规则控制、分层多智能体控制、社区进出口限制 | `src/controllers/`、`src/coordination/` |
| 电网仿真 | 将建筑功率映射到配电网，计算潮流、电压与线路负载 | pandapower adapter |
| 评估 | 能源、服务、电网、智能体及成员级指标，图表和报告 | `src/evaluation/` |
| 智能体流程 | 规划、生成代码、沙箱执行、验证、修复与报告 | `src/agents/` |
| 结果前端 | 浏览已保存运行、空间图层、资产和时间步 | `frontend/` 中的 React、TypeScript、MapLibre、deck.gl 和 Plotly |

当前联合仿真顺序为：获取 CityLearn 观测、请求并应用控制器动作、将所得建筑功率传给 pandapower，随后将电网诊断与仿真时间步一同记录。电网回路现在可闭合：检测到违规（pandapower 诊断）→ `controller.update_grid_diagnostics` → 重新调度 → 再次检查潮流，持续在 `SimulationCoupler.step` 内运行。指标跟踪每次运行中违规已解决 vs 尝试的次数；重新调度动作记录在 `result.json` 中。

## 仓库结构

```text
.
  configs/                 # 情景 A 的 YAML 配置
  data/schemas/            # CityLearn schema 和情景数据
  experiments/
    run_experiment.py      # 运行单次情景/控制器实验
    run_benchmark.py       # 运行情景/控制器/随机种子组合
    ...                    # 已保存实验输出与摘要
  frontend/                # React + TypeScript + Vite 应用
  src/
    api/                 # FastAPI 生产服务（单一入口）
    agents/              # Planner、Coder、Executor、Verifier、Repair 和 Reporter
    controllers/         # 规则型、集中式启发式和多智能体控制器
    coordination/       # 建筑/资源智能体和社区聚合器
    evaluation/          # 能源、服务、电网、公平性指标和图表
    schemas/             # Pydantic 情景、动作、诊断和报告模型
    simulation/          # CityLearn adapter、pandapower adapter 和联合仿真
    tests/                   # Python 自动化测试
  backend/                 # 规范的 FastAPI 应用（入口：backend.app.main:app）
    app/                # 路由：agent、scenarios、simulations、network、reports、compare
  project brief.md         # 完整产品/研究需求和目标里程碑
  notes.md                 # 研究和出版规划笔记
```

关键顶级目录：`backend/`（FastAPI 服务，`/api/*`、`/ws`），`frontend/`（React + Vite 应用），`src/`（仿真、控制器、协调、智能体、评估），`experiments/`（运行器、矩阵、论文图表），`configs/`、`data/`、`docs/`、`arxiv_submission/`、`scripts/`、`tests/`。

生成的运行结果写入所选输出目录。除非刻意作为可复现发布物的一部分，否则请勿提交大型轨迹文件或绘图产物。

## 实验情景

当前所有情景均描述五栋建筑的社区，配置在 `configs/` 中。

| 文件 | 计划研究内容 | 当前配置状态 |
|---|---|---|
| `scenario_a.yaml` | 带光伏、电池、EV、柔性负载和分时电价的基准社区 | 基准实验配置 |
| `scenario_b.yaml` | 更高 EV 渗透率和早/晚充电截止时间 | 情景配置已有；运行结果仍需验证 |
| `scenario_c.yaml` | 更高光伏渗透率、外送和电网约束 | 情景配置已有；运行结果仍需验证 |
| `scenario_d.yaml` | 本地能源共享和结算 | 已声明共享设置；市场执行和结算尚未端到端实现 |
| `scenario_e.yaml` | 光伏、电池、充电器、传感器和电网限制故障 | 已声明故障情景；运行时注入和恢复尚未端到端实现 |

## 指标与实验设计

评估代码定义了以下类别的指标：

- **能源与成本：** 总成本、电网购电/外送、峰值需求、负荷率、光伏发电/自用/弃电、电池吞吐量/循环数及碳排放。
- **参与者服务：** EV 完成率和离站 SOC、舒适度违规度时、柔性负载完成率/延迟、需求响应交付及每成员结果。
- **电网可行性：** 潮流收敛、电压边界和违规、线路/变压器负载、社区购电/外送限制。
- **智能体执行：** 任务和仿真成功率、首次有效率、修复迭代次数、运行时间和报告完整性。

`experiments/run_benchmark.py` 支持 `rule_based`、`multi_agent`、`centralized`、`mpc` 和 `rl` 控制器标签。`mpc` 是确定性的滚动时域线性规划；`rl` 是从 `experiments/rl_policy/<scenario>.json` 加载的表格 Q-learning 策略。`centralized` 实现仍是启发式控制器，而非优化器。控制器按已公开资产 ID（`{building}_battery`、`{building}_ev_{i}`、`{building}_flex_{i}`）请求 kW 功率；CityLearn adapter 利用实时设备额定值将这些转换为模拟器的归一化设备动作。benchmark 脚本为每种配置运行独立进程，支持并行 worker，并报告均值、样本标准差和 Student-t 95% 置信区间。详见 `experiments/BENCHMARK_MATRIX.md`（计划矩阵、随机种子、运行时间预算和已知测量注意事项）。一次小型 smoke run 不足以作为论文主张的证据。

> **修复前的 benchmark 数字无效。** 种子可复现性修复（PR #1）之前生成的 benchmark 结果未给所有随机源设定种子，无法复现，必须不予引用。使用任何数字前，请用当前代码重新运行 benchmark；复现性门禁见 [`docs/reproducibility.md`](docs/reproducibility.md)。

## 安装与运行

### 快速入门（约 10 分钟）

获得运行中 UI 的最短路径，含一次真实运行：

```bash
# 1. Python 环境 + 包
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -e .

# 2. 一次快速实验（写入 results/<情景>/<运行>/）
python experiments/run_experiment.py \
  --config configs/scenario_a.yaml --controller rule_based --seed 42 --max-steps 96

# 3. 后端 API（提供 /api/* 和 /ws，默认端口 8001，与 Vite 代理匹配）
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8001

# 4. 前端（另开一个终端）
npm --prefix frontend install
npm --prefix frontend run dev                     # http://127.0.0.1:3000
```

打开 Vite 地址，在 Community Canvas 上选择刚产生的运行。从顶栏样式控件切换视觉样式（GE Vernova / Schneider / dark）。若 API 托管在其他位置，请设置 `VITE_API_BASE_URL` / `VITE_WS_BASE_URL`（见 `frontend/.env.example`）。

### 环境变量

| 变量 | 位置 | 用途 |
|---|---|---|
| `VITE_API_BASE_URL`, `VITE_WS_BASE_URL` | `frontend/.env` | 将前端指向独立的 API/WebSocket 服务 |
| `VITE_MAPBOX_TOKEN` | `frontend/.env` | 可选；默认使用 Carto 底图 |
| `AGENT_BACKEND` | shell / `.env` | 托管 LLM 后端，例如 `api:poolside/laguna-xs-2.1` |
| `LLM_BASE_URL`, `LLM_API_KEY` | shell / `.env` | 托管 LLM 端点和密钥（密钥永不提交） |
| `NVIDIA_API_KEY` | shell / `.env` | NVIDIA NIM 后端的密钥（`poolside/laguna-xs-2.1` 通过环境变量注入，绝不硬编码；`kimi-k2.7-code` 额度已耗尽，不可用） |

完整列表见 `frontend/.env.example` 和根目录 `.env.example`。

### Python 仿真

使用 Python 3.10 或更新版本。从仓库根目录运行：

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
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

支持的控制器参数为 `rule_based`、`multi_agent`、`centralized`、`mpc` 和 `rl`。可选参数包括 `--max-steps`、`--output-dir`、`--seed`、`--run-id` 和 `--rl-policy`（`rl` 时必填）。

先训练表格 Q-learning 基线再运行 `rl` 控制器。训练写入 `experiments/rl_policy/`（已 gitignore）；benchmark 矩阵的精选策略已检入 `experiments/reference/rl_policy/`。

```powershell
python -m experiments.train_rl `
  --config configs/scenario_a.yaml `
  --out experiments/rl_policy/scenario_a.json `
  --episodes 60
```

运行小型 benchmark，例如：

```powershell
python experiments/run_benchmark.py `
  --scenarios configs/scenario_a.yaml `
  --controllers rule_based multi_agent `
  --seeds 42 123 `
  --output experiments/benchmark_test
```

benchmark 命令默认运行情景 A–E、五种控制器标签和五个随机种子（42、123、456、789、999）。使用 `--workers N` 并行运行配置，并用 `--rl-policy-dir` 指向每种情景的 RL 策略。完整运行需要数小时而非数分钟：按 `experiments/BENCHMARK_MATRIX.md` 中的每运行测量时间预算。`experiments/run_all.sh` 是 Bash 脚本；Windows 下请使用 Git Bash、WSL 或其他 Bash 环境。

### React 前端

需要 Node.js 和 npm。从仓库根目录：

```powershell
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run dev -- --host 127.0.0.1
```

打开 Vite 地址，通常为 `http://127.0.0.1:3000/`。VS Code 也配置了 **Run Virtual Community Frontend** 任务。

构建并类型检查前端：

```powershell
npm.cmd --prefix frontend run build
```

### 本地结果 API

Vite 开发服务器内置只读本地中间件，扫描仓库 `results/` 目录中的 `result.json` 文件，并提供运行摘要和同目录 `trajectories.jsonl` 文件。这是开发便利功能，**不是生产后端**。前端 API 客户端还定义了情景、仿真、智能体、报告、比较和 WebSocket 端点；一个匹配的 FastAPI 服务目前尚未包含在本仓库中。连接独立服务时设置 `VITE_API_BASE_URL` 和 `VITE_WS_BASE_URL`。

## React 前端

默认路由是社区画布，包括：

- 基于已保存实验结果的运行选择。
- 带 deck.gl 图层的 MapLibre 底图：建筑、光伏、电池、EV、馈线、变压器、违规、热图和能量流。
- 带播放/暂停、逐步、重置和速度控制的时间滑块。
- 上下文相关的资产/电网检查器。
- Scenario Studio、Agent Workspace、报告和运行比较路由。
- **可切换视觉样式** — `GE Vernova`（默认，浅色企业风格）、`Schneider`（浅色，绿色）和 `dark` 画布。从顶栏样式控件切换；通过 `<html data-theme>` 和 `frontend/src/config/theme.ts` 实现。设计笔记：`docs/frontend_visual_direction.md`。
- **配色方案** — chrome 和焦点使用 IEEE 蓝色强调色（`#00C0EF`），地图上的中性定位价格坡度；红色专用于违规。Agent Workspace 使用水平 `Plan → Code → Execute → Verify → Repair → Report` 轨道（设计：`docs/phase4_agent_workspace_design.md`）。

当前地图位置和馈线几何是示意值，而非实际 pandapower 网络。从已保存结果加载时，运行数据是真实实验数据，但若干可视化和工作流元素仍不完整：未映射真实电网拓扑，部分设备状态是从观测/动作推断的，情景/智能体/报告操作依赖仓库尚未提供的后端路由。

## 测试与当前验证状态

从仓库根目录运行测试：

```powershell
pytest -q tests
```

套件涵盖控制器协同、CityLearn adapter 行为、pandapower adapter 行为、指标、benchmark 主管和智能体修复脚手架。**完整套件当前通过**，包括针对 CityLearn adapter 时间步约定和控制器动作接口（kW 请求到归一化 CityLearn 动作，包括资产 ID 别名和 EV 观测来源）的回归测试。

## 当前限制

- **非生产级 VPP。** FastAPI 服务（`backend/`）是本地/开发 API（无认证，localhost CORS），Vite `results/` 中间件仅为开发便利功能。
- **LMP 分支在拥堵情况下以回退为主。** 在 M1 `lmp` 运行中，OPF 回退（`power_flow_not_converged`），每运行价格指标不可用（零/负测量价差），因此无法从中产生有效的定位价格扩散结果（图 F8）。
- **P2P 未调度。** 匹配引擎和 schema 已存在并经过测试，但未执行任何 `p2p` 运行，也没有 P2P WebSocket 端点。
- **电网反馈环为部分。** 违规会被记录且重新调度存在，但未在所有情况中证明完整的验证闭环。
- **示意几何。** 地图位置和馈线几何为示意值，而非实际 pandapower 网络；前端时间标签假设 15 分钟步长。
- **Benchmark 覆盖。** 矩阵覆盖主要控制器和定价机制；论文级 MPC/RL 和未验证 vs 已验证智能体比较仍在扩展中。

## 后续路线

1. **DONE** — 恢复干净的测试基线，统一时间步/数据单元契约。
2. **DONE** — 定价机制（pool-TOU / LMP）、P2P 匹配 + schema、配置化故障注入（场景 E）、plan → code → execute → verify → repair 智能体工作流，以及带可切换样式 React 前端的 FastAPI 服务。
3. 关闭联合仿真回路，使电网诊断能够约束或触发经过验证的重新调度。
4. 让 LMP 分支在拥堵情况下产生有效的定位价格（修复 OPF 回退），使价格扩散结果具备论文级可信度。
5. 调度并验证 `p2p` 运行；增加 P2P WebSocket 端点。
6. 运行完整 benchmark 矩阵，配合可复现随机种子、适当基线和统计分析。

当前真正待办的是第 4 项（LMP OPF 回退修复）和第 5 项（P2P 调度运行）。完整产品规格、首个里程碑验收标准和论文定位见 [`project brief.md`](project%20brief.md)。

## 部署

生产部署指南见 [`docs/deployment_guide.md`](docs/deployment_guide.md)，运维规范见 [`docs/production_ops.md`](docs/production_ops.md)。

## 许可证

项目元数据声明使用 MIT。重新分发前，请确认仓库许可证文件及第三方素材的授权条款。
