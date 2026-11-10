# 可再生能源社区虚拟仿真器

**简体中文** | [English](README.md)

一个基于物理模型的时空虚拟社区仿真器——带有屋顶光伏、电池、电动汽车和柔性负荷的建筑社区，运行在真实的配电网之上——并配备一个贯穿整个工程流程的 **Coding Agent 智能助手**。该助手**不是**第五种控制算法：它负责构建场景、生成与修改控制策略、分析仿真结果、诊断违规，并提出可验证的修正方案。

平台主循环：

```text
自然语言描述
  → Coding Agent → 经过验证的仿真配置（ScenarioConfig）
  → 虚拟社区 → 仿真（CityLearn + pandapower）
  → 时空可视化
  → 策略比较（ rule-based / MPC / 单智能体 RL / 多智能体 RL ）
  → 智能助手辅助优化（可验证、经闸门检查）
```

同一平台内的五个工作流阶段：**场景构建 → 仿真 → 可视化 → 策略比较 → 智能助手辅助优化。**

> **项目状态（2026-11-10）：** 已重新聚焦于仿真器平台。已建成并通过测试：物理核心（CityLearn + pandapower 耦合，含闭环重调度）、完整场景 schema、场景 CRUD API、四种控制策略、带验证闸门的智能体工作流，以及 React 社区画布。进行中：自然语言 → ScenarioConfig 管道（阶段 1）。智能体的策略修改组件实测 **5/9 通过检测器验证的修改**（预登记阈值 ≥7/9 未达成，两向如实报告）——是真实但低于阈值的能力，不是控制策略结果。引用任何数字前请参阅[当前状态](#当前状态与阶段计划)。

## 目录

- [当前状态与阶段计划](#当前状态与阶段计划)
- [研究问题](#研究问题)
- [系统架构](#系统架构)
- [仓库结构](#仓库结构)
- [场景](#场景)
- [指标与实验设计](#指标与实验设计)
- [安装与运行](#安装与运行)
- [React 前端](#react-前端)
- [测试与当前验证](#测试与当前验证)
- [当前限制](#当前限制)
- [路线图](#路线图)

## 当前状态与阶段计划

项目负责人已将项目重新聚焦于 [`project brief.md`](project%20brief.md) 所描述的虚拟社区仿真器：平台是产品，智能体是助手。阶段顺序：

| 阶段 | 内容 | 状态 |
|---|---|---|
| **P1** | 自然语言 → ScenarioConfig 管道：用自然语言描述社区，智能体产出经过验证、可审查的仿真配置 | 进行中——后端管道、评测语料、确认交互 UX（规范：`docs/nl_config_confirm_design.md`）、输入界面 |
| **P3** | 智能助手范围：物理/服务闸门下的策略生成与修改、结果分析、诊断、可验证提案 | 组件已存在（规划 → 代码 → 执行 → 验证 → 修复）。实测：5/9 检测器验证的修改，阈值 ≥7/9 未达成 |
| **P4** | 论文围绕平台重构（代码修复结果降为支撑结果） | 待定 |
| **P2** | 时空虚拟社区可视化与策略比较视图 | 最后阶段 |

记录在案的控制策略（在相同场景下比较）：**rule-based、MPC、单智能体 RL、多智能体 RL**（`centralized` 启发式仍属启发式控制器）。LLM/代码智能体永不作为控制器进入比较。

LLM 授权记录：NVIDIA NIM 上的 `poolside/laguna-xs-2.1`（不足时才改用 DeepSeek 4.1）。未授权其他模型。

## 研究问题

本项目的核心问题：

> 一个以物理模型为基础的建筑–电网耦合仿真器，配以工程助手角色的代码智能体，能否在保障个体服务质量与配电网约束的前提下，完成可再生能源社区场景的构建、仿真、诊断、比较与改进？

系统评价的不只是总成本或电网进口量，还包括：个体 EV 是否满足离站 SOC 目标、建筑是否维持在舒适区间、能源资源如何被使用，以及耦合的配电网是否保持可行。

## 系统架构

| 层 | 职责 | 主要实现 |
|---|---|---|
| 社区仿真 | 建筑需求、光伏、储能、EV、柔性负荷、观测与动作 | CityLearn v3 适配器 |
| 协调 | Rule-based、MPC、RL 控制；分层多智能体控制；社区进口/出口限制 | `src/controllers/`、`src/coordination/` |
| 电网仿真 | 将建筑功率映射到配电网并评估潮流、电压与负载率 | pandapower 适配器 |
| 评测 | 能源、服务、电网、公平性指标；图表与报告 | `src/evaluation/` |
| 场景服务 | 自然语言场景构建、场景 CRUD、校验 | `backend/app/routers/scenarios.py`、`src/schemas/scenario.py` |
| 智能体工作流 | 规划、生成代码/配置、沙箱执行、验证、修复、报告 | `src/agents/` |
| 结果界面 | 浏览已保存运行、空间图层、资产与仿真时间步 | `frontend/`（React、TypeScript、MapLibre、deck.gl、Plotly） |

当前协同仿真序列：获取 CityLearn 观测 → 请求并应用控制器动作 → 将建筑功率传入 pandapower → 随仿真步记录电网诊断。电网闭环已经打通：检测到违规（pandapower 诊断）→ 控制器 update_grid_diagnostics → 重调度 → 潮流复检，在 SimulationCoupler.step 内持续运行。指标跟踪每次运行中“已解决/已尝试”的违规数；重调度动作记录在 result.json。

## 仓库结构

```text
.
  configs/                 # 场景 A YAML 配置
  data/schemas/            # CityLearn schema 与场景数据
  experiments/
    run_experiment.py      # 运行单个场景/控制器实验
    run_benchmark.py       # 运行场景/控制器/随机种子组合
    ...                    # 已保存的实验输出与摘要
  frontend/                # React + TypeScript + Vite 应用
  src/
    api/                 # FastAPI 生产服务（单一入口）
    agents/              # 规划、代码、执行、验证、修复与报告
    controllers/         # Rule-based、集中式启发式与多智能体控制器
    coordination/       # 建筑/资源智能体与社区聚合器
    evaluation/          # 能源、服务、电网、公平性指标与图表
    schemas/             # Pydantic 场景、动作、诊断与报告模型
    simulation/          # CityLearn 适配器、pandapower 适配器与协同仿真
    tests/                   # Python 自动化测试
  backend/                 # 规范 FastAPI 应用（入口：backend.app.main:app）
    app/                # 路由：agent、scenarios、simulations、network、reports、compare
  project brief.md         # 完整产品/研究简报与目标里程碑
  notes.md                 # 研究与发表规划笔记

```

关键顶层目录：`backend/`（FastAPI 服务：`/api/*`、`/ws`）、`frontend/`（React + Vite 应用）、`src/`（仿真、控制器、协调、智能体、评测）、`experiments/`（运行器、矩阵、论文图）、`configs/`、`data/`、`docs/`、`arxiv_submission/`、`scripts/`、`tests/`。

生成的运行写入所选输出目录。除非是有意的可复现构件，避免提交大型生成轨迹或图表。

## 场景

当前所有场景均描述五建筑社区，配置在 `configs/`。

| 文件 | 预期研究 | 配置状态 |
|---|---|---|
| `scenario_a.yaml` | 基线社区：光伏、电池、EV、柔性负荷与分时电价 | 基线实验配置 |
| `scenario_b.yaml` | 更高 EV 渗透率与早晚离站截止 | 场景配置；运行结果待验证 |
| `scenario_c.yaml` | 更高光伏渗透率、出口与电网约束 | 场景配置；运行结果待验证 |
| `scenario_d.yaml` | 本地能源共享与结算 | 共享设置已声明；市场执行与结算尚未端到端实现 |
| `scenario_e.yaml` | 光伏、电池、充电桩、传感器与电网限额故障 | 故障用例已声明；运行时注入与恢复尚未端到端实现 |

## 指标与实验设计

评测代码定义以下指标组：

- **能源与成本：** 总成本、电网进口/出口、峰值需求、负荷率、光伏发电/自消耗/弃电、电池吞吐/循环、碳排放。
- **参与者服务：** EV 完成率与离站 SOC、舒适度违规度时、柔性负荷完成率/延迟、需求响应履约与逐成员结果。
- **电网可行性：** 潮流收敛率、电压限值与违规、线路/变压器负载率、社区进口/出口限制。
- **智能体执行：** 任务与仿真成功率、首次尝试有效性、修复迭代次数、运行时与报告完整性。

`experiments/run_benchmark.py` 支持 `rule_based`、`multi_agent`、`centralized`、`mpc`、`rl` 控制器标签。`mpc` 为确定性滚动时域线性规划；`rl` 为从 `experiments/rl_policy/<scenario>.json` 加载的表格型 Q-learning 策略。`centralized` 实现仍是启发式控制器，不是优化器。控制器以 kW 在公开资产 ID（`{building}_battery`、`{building}_ev_{i}`、`{building}_flex_{i}`）下请求功率；CityLearn 适配器使用实时设备额定值将其转换为仿真器的归一化设备动作。基准脚本为每个配置独立进程运行，支持并行 worker，报告均值、样本标准差与 Student-t 95% 置信区间。见 `experiments/BENCHMARK_MATRIX.md` 了解计划矩阵、种子、运行时长预算与已知测量注意事项。小规模冒烟运行不足以作为论文结论的证据。

> **修复前的基准数字无效。** 种子可复现性修复（PR #1）之前生成的基准结果未播种所有随机源，无法复现，不得引用。使用任何数字前请用当前代码重跑基准；见 [`docs/reproducibility.md`](docs/reproducibility.md) 的可复现性闸门。

## 安装与运行

### 快速开始（约 10 分钟）

到达可运行界面与一次真实运行的最短路径：

```bash
# 1. Python 环境 + 包
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -e .

# 2. 一次快速实验（写入 results/<scenario>/<run>/）
python experiments/run_experiment.py \
  --config configs/scenario_a.yaml --controller rule_based --seed 42 --max-steps 96

# 3. 后端 API（提供 /api/* 与 /ws，默认端口 8001，与 Vite 代理匹配）
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8001

# 4. 前端（另开终端）
npm --prefix frontend install
npm --prefix frontend run dev                     # http://127.0.0.1:3000
```

打开 Vite 网址，在社区画布上选择刚产生的运行。在顶栏的样式控制器切换视觉样式（GE Vernova / Schneider / dark）。若 API 部署在别处，设置 `VITE_API_BASE_URL` / `VITE_WS_BASE_URL`（见 `frontend/.env.example`）。

### 环境变量

| 变量 | 位置 | 用途 |
|---|---|---|
| `VITE_API_BASE_URL`、`VITE_WS_BASE_URL` | `frontend/.env` | 将前端指向独立的 API/WebSocket 服务 |
| `VITE_MAPBOX_TOKEN` | `frontend/.env` | 可选；默认使用 Carto 底图 |
| `AGENT_BACKEND` | shell / `.env` | 托管 LLM 后端，如 `api:poolside/laguna-xs-2.1` |
| `LLM_BASE_URL`、`LLM_API_KEY` | shell / `.env` | 托管 LLM 端点与密钥（密钥从不提交） |

完整列表见 `frontend/.env.example` 与根 `.env.example`。

### Python 仿真

需要 Python 3.10 或更高版本。在仓库根目录：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

运行单个实验：

```powershell
python experiments/run_experiment.py `
  --config configs/scenario_a.yaml `
  --controller rule_based `
  --seed 42
```

支持的控制器参数为 `rule_based`、`multi_agent`、`centralized`、`mpc`、`rl`。可选参数包括 `--max-steps`、`--output-dir`、`--seed`、`--run-id`、`--rl-policy`（`rl` 必需）。

运行 `rl` 控制器前需先训练表格型 Q-learning 基线。训练写入 `experiments/rl_policy/`（gitignored）；基准矩阵用的精选策略签入在 `experiments/reference/rl_policy/`。

```powershell
python -m experiments.train_rl `
  --config configs/scenario_a.yaml `
  --out experiments/rl_policy/scenario_a.json `
  --episodes 60
```

运行一个小规模基准，例如：

```powershell
python experiments/run_benchmark.py `
  --scenarios configs/scenario_a.yaml `
  --controllers rule_based multi_agent `
  --seeds 42 123 `
  --output experiments/benchmark_test
```

基准命令默认为场景 A-E、五个控制器标签、五个种子（42, 123, 456, 789, 999）。用 `--workers N` 并行运行配置，用 `--rl-policy-dir` 指定各场景 RL 策略目录。完整运行需要数小时而非数分钟：请按 `experiments/BENCHMARK_MATRIX.md` 中的实测单次运行时间编制预算。`experiments/run_all.sh` 是 Bash 脚本；Windows 上请使用 Git Bash、WSL 或其他 Bash 环境。

### React 前端

需要 Node.js 与 npm。在仓库根目录：

```powershell
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run dev -- --host 127.0.0.1
```

打开 Vite 网址，通常为 `http://127.0.0.1:3000/`。也已配置名为 **Run Virtual Community Frontend** 的 VS Code 任务。

构建与类型检查前端：

```powershell
npm.cmd --prefix frontend run build
```

### 本地结果 API

Vite 开发服务器包含一个只读本地中间件，扫描仓库 `results/` 目录中的 `result.json` 文件并提供运行摘要与相邻 `trajectories.jsonl` 文件。这是开发便利，**不是**生产后端。前端 API 客户端还定义了场景、仿真、智能体、报告、比较与 WebSocket 端点；本仓库目前不包含匹配的 FastAPI 服务。连接独立服务时请设置 `VITE_API_BASE_URL` 与 `VITE_WS_BASE_URL`。

## React 前端

默认路由是社区画布，包含：

- 由已保存实验结果支持的运行选择。
- MapLibre 底图 + deck.gl 图层：建筑、光伏、电池、EV、馈线、变压器、违规、热力图与能流。
- 带播放/暂停、步进、重置与速度控制的时间滑块。
- 上下文相关的资产/电网检查器。
- 场景工作室、智能体工作区、报告与运行比较路由。
- **可切换视觉样式** — `GE Vernova`（默认，浅色企业风）、`Schneider`（浅色，绿）、`dark` 画布。在顶栏样式控件切换；以 `<html data-theme>` 与 `frontend/src/config/theme.ts` 实现。设计说明：`docs/frontend_visual_direction.md`。
- **配色方案** — IEEE 蓝强调色用于界面与焦点（`#00C0EF`），地图上用中性区位价格渐带；红色专用于违规。智能体工作区使用水平 `Plan → Code → Execute → Verify → Repair → Report` 导轨（设计：`docs/phase4_agent_workspace_design.md`）。

当前地图位置与馈线几何为示意性质。从已保存结果加载时运行数据是真实的，但若干视觉与工作流元素尚不完整：未映射实际电网拓扑，部分设备状态由观测/动作推断，场景/智能体/报告操作需要尚未提供的后端路由。

## 测试与当前验证

在仓库根目录运行测试：

```powershell
pytest -q tests
```

测试套件覆盖控制器协调、CityLearn 适配器行为、pandapower 适配器行为、指标、基准监督器与智能体修复脚手架。**全套通过**，包括 CityLearn 适配器时间步约定与控制器动作接口（kW 请求到归一化 CityLearn 动作，含资产 ID 别名与 EV 观测来源）的回归测试。

## 当前限制

- **不是生产级 VPP。** FastAPI 服务（`backend/`）是本地/开发 API（无鉴权、localhost CORS），Vite `results/` 中间件仅为开发便利。
- **自然语言场景构建进行中。** 场景 schema 与 CRUD API 已存在，智能体的配置创作管道正在建设；在阶段 1 落地前，场景通过 YAML 配置或 API 创建，而非自然语言。
- **智能体策略修改低于其预登记阈值。** 在组件基准上，智能体在 5/9 实测用例中产出检测器验证的修改（阈值 ≥7/9 未达成，两向如实报告）。这是组件结果，不是控制策略结果。
- **LMP 支路在拥塞用例上回退居多。** 在 M1 `lmp` 运行中 OPF 回退（`power_flow_not_converged`），逐次运行价格指标不可用（实测价差为零/负），因此尚无法从中产出有效的区位价格离散结果（图 F8）。
- **P2P 未排期运行。** 撮合引擎与 schema 已存在并通过测试，但没有执行 `p2p` 运行，也没有 P2P WebSocket 端点。
- **电网反馈闭环不完整。** 违规已记录且重调度存在；全案例的完整验证闭环尚未证明。
- **示意性几何。** 地图位置与馈线几何为示意，非实际 pandapower 网络；前端时间标签假定 15 分钟步长。
- **基准覆盖。** 矩阵覆盖主要控制器与定价机制；论文级 MPC/RL 与未验证 vs 已验证智能体比较仍在扩展中。

## 路线图

1. **已完成** — 恢复干净的测试基线，统一时间步/数据单位约定。
2. **已完成** — 定价机制（pool-TOU / LMP）、P2P 撮合 + schema、可配置故障注入（场景 E）、规划 → 代码 → 执行 → 验证 → 修复智能体工作流，以及带可切换样式的 React 前端的 FastAPI 服务。
3. **阶段 1（进行中）** — 自然语言 → ScenarioConfig 管道：智能体的场景构建前门，含确认闸门；评测语料；输入 UX。
4. **阶段 3** — 智能助手范围：物理/服务闸门下的策略生成与修改、结果分析、诊断、可验证提案。
5. **阶段 4** — 论文重构：以平台为贡献；代码修复/策略修改结果为支撑结果。
6. **阶段 2（最后）** — 时空虚拟社区可视化与策略比较视图。
7. 打通协同仿真闭环，使电网诊断能约束或触发经验证的重调度；修复拥塞用例上的 OPF 回退以产出有效区位价格；排期并验证 `p2p` 运行。

完整产品规格、首个里程碑验收标准与论文定位见 [`project brief.md`](project%20brief.md)。

## 许可证

项目元数据声明 MIT。再分发前请确认仓库的许可证文件与第三方素材条款。
