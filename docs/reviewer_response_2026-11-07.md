# 對外部審查意見的回應（2026-11-07）

回應人：Research Engineer（基準與論文結果負責人）。
審查對象：8 頁 `arxiv_main.pdf`（編譯於 2026-11-04 之前）。

## 0. 首要前提：審稿版本與現況的時間差

審稿意見整體公允，我們接受「Major Revision」的定位。但必須先說明一個時間差：
審稿所讀的 PDF 反映的是 **PV 迴歸修復之前**的資料狀態（部分數字來自合成物理
與故障資料樹）。其後（11/4–11/7）我們完成並驗證了：

1. **750-run B-axis 基準**（全部在修復後物理上執行，`git_dirty=False`，
   commits `0911a6f/210d35d/0e584b7`）：pool_tou 250 + p2p 250 + LMP 250
   （**含 RL 行**），每矩陣 10 seeds。
2. **PV 數據取證與對賬**（`docs/paper_rescope_assessment.md` @ 21d3c3a）：
   14.5（命名缺口→dummy）、1455.3（舊機器、4 月窗口）、14528.1（×1000 過衝
   時代）、**1914.8（正確，第一性原理驗證 +0.00%）**。
3. **M5.2/M2a 重定範圍評估**：哪些表可重建、哪些須重跑（M2a 絕對值、aggressive）。

以下逐點回應，標註【接受】【已解決】【部分接受】【開放】。

## 1. 逐項回應

### 實驗數量不一致（P0）【接受，已重建】
審稿人推算 320 的方向正確；該 PDF 的「175」確實無法涵蓋全部。以 run
manifests 為準的現況：**750（B-axis：pool_tou 250 + p2p 250 + LMP 250，各
10 seeds）+ M2a 45 + aggressive 20 = 815**，另加歷史 release artifact
（035a52f，125+50）僅作 provenance。新表格將逐一以 manifest 目錄為準重建
（`matrix_full` / `matrix_p2p` / `m52_benchmark`）。

### Abstract 成本區間不完整（P0）【接受，數據已更新】
−17.68 至 −41.37 摘自舊樹。新 10-seed 數據的 multi_agent vs rule_based
配對差（scenario_a）：**−18.11 ± 0.03 USD，p_Holm < 1e-4**；全場景、全控制器
的 Holm 校正配對差已計算完畢，重建 Table 2 時按新數據重寫摘要區間。
**未決項**：scenario D 與 A 在新樹上逐位相同（config 傳播待查，見 §4），
D 列修復前不進 Table 2。

### LLM 主張過強（P0/P1）【接受】
同意。0 repairs 不是 repair capability 的展示，而是「在該 proposer 條件下
verification 未被觸發」的 null result。Abstract 將改寫為：verified workflow
的安全性判別未在該模型/提示/視窗下被觸發（誠實的 null result），並把
「Physics-grounded verification of LLM-generated controller repairs」定為
唯一主線——正是審稿人建議的定位。

### Table 5 缺統計檢定（P0）【接受，已補計算】
新計算（n=15 配對 (scenario, seed)，對照 multi_agent reference 的配對差）：
- unverified：+1.370 ± 0.982 USD；verified：+0.099 ± 0.159 USD
- **臂間差（unverified − verified）：+1.271 ± 1.015 USD，paired t=2.686，
  p=0.018**；peak：+9.86 kW，paired t=2.334，p=0.035
解讀保持審慎：這顯示 verified 臂更貼近 reference（成本/peak 的次優性較小），
**不**構成 safety benefit 的證明（期間 0 violations、0 repairs）。論文將照此
措辭。

### 失效注入只證明偵測（Major Concern 3）【接受】
同意偵測 ≠ 復原。新數據中 Scenario E 的新矩陣（10 seeds）保留偵測與記錄
結論；「恢復能力」將從主張中移除，改列為 M2b/復原實驗的待驗證問題。

### 相關工作不足（P1/P3）【接受】
將補入審稿人列出的五項近鄰工作（Agentic HEM 2026、intent-driven state
verification 2026、ElecBench 2025、PowerAgentBench-SS 2026、smart-grid MAS
survey 2024），並以審稿人建議的差異化主張組織：**LLM 不直接控制物理系統，
而是修改控制器，修改須經模擬器 + 電網驗證 + 服務級檢查**。同時補 CityLearn
v2/v3 版本文獻（實際使用 3.0.2）。

### 可重現性（P1/P3）【部分接受】
- 同 seed 重複執行一致性：接受為缺口。計畫：單一 config 重複 3 次，斷言
  KPI 逐位一致（成本低，將加入）。
- 統計方法交代：補充規格——配對雙側 Student-t（按 seed 配對）、95% CI 為
  t(0.975, n−1)·s/√n、Holm family = 每場景內 4 個控制器對 rule_based 的比較；
  n 已由 5 增至 10。
- Release artifact 連結/DOI：QA 打包三矩陣 zip + SHA256SUMS + INDEX.json 後
  補上（重定範圍文件 §6.5 已列）。

### 情境 D 熱舒適與 Table 2（P0）【接受，開放中】
新發現：**scenario D 與 A 在新樹上逐位相同**（member bills 與 gini 完全一致，
config hash 卻不同）——D 的能源共享配置未在模擬中生效，屬 config 傳播問題，
已列待 Backend 查證。修復並重跑 D（~50 runs）之前，Table 2/3 的 D 列不重建。
這同時回應「Table 2 缺 D 數字」與「D comfort 未報告」兩點。

### 服務指標可測性：thermal comfort（P2）【接受，已查證】
審稿人要求完整報告 EV 與熱舒適。EV 已完整報告（見 `docs/item7_service_and_failures/`：
completion、avg/worst SOC at departure，逐場景 x 控制器，10 seeds）。**熱舒適在
本資料集上不可測**：CityLearn 2022 stock dataset 的
`indoor_dry_bulb_temperature` 整欄為 NaN，`src/evaluation/metrics.py` 的
comfort band 判定因此恆為 0——750-run B-axis + 150-run D 重跑中
`comfort_violation_degree_hours` 皆為 0.0（250 個場景/控制器單元，min = max）。
這是**資料可得性結果，不是「沒有熱舒適違規」**。論文必須明講：
(a) comfort_violation_degree_hours = 0.0 標註為資料缺失（all-NaN 序列）的產物；
(b) 不得宣稱「no comfort violations」；(c) 22.0 °C 的填補（commit `705923481`）
只是讓 gymnasium ≥ 1.1 能建構 observation space 的環境必要性，不是舒適資料，
不改變任何已報告數字（comfort 仍為 0.0，與修復前一致）。若要有舒適主張，
需要含室內溫度的資料集或 CityLearn 建築熱模型——在此之前舒適列為超出範圍。

### 作者資訊（P0）【接受，已解決 2026-11-08】
`OpenBot Platform`/`.local` email 的 placeholder 已由用戶提供真實作者資訊取代：
第一作者 Wong Wah Cheng（The Hong Kong Polytechnic University）、第二作者
OpenBot，無 author roles（無 `\thanks`、無 corresponding-author 標記，依用戶
裁定）。Paste-ready LaTeX 在 `docs/author_block.md`（main @ `42327f4085`）：
以單次貼上取代 `arxiv_submission/arxiv_main.tex` 第 38-42 行的 author block。
本團隊不編輯 `arxiv_submission/`（用戶擁有），此檔只提供確切文字。

### 寫作與結構（P3）【接受】
Intro 重複合併、移除內部開發紀錄措辭、補系統架構圖、dual decomposition
公式與收斂說明、Agent end-to-end 案例（含 patch diff 與修復前後指標）——
全部納入修改清單。

## 2. 我們不同意或需補充之處（少量）

1. 「核心證據不足 → Agent 定位 4/10」：在**修復前資料**上成立；修復後的新
   數據已將 LMP 矩陣補至 10 seeds 含 RL、新增 P2P 制度與配對統計。Agent
   主線的核心實驗（M2b 型 hostile-proposer）確實仍缺——見 §3。
2. 「無法核對 320」：已核對，實際為 815（見 §1），manifest 目錄可逐一驗證。

## 3. 修改路線（按審稿人 P0–P3 對齊）

- **P0（文件，~1–2 天）**：以 750-run 數據重建 Table 2/3/4/5；統一 run
  數（815）；補 Table 5 配對檢定（已算好）；改寫 Abstract null 措辭；清理
  Intro；作者資訊（用戶）。**阻擋項：scenario D config 傳播修復**。
- **P1（實驗，~1 週）**：hostile-proposer M2b——注入格式破壞/越界提案、提高
  溫度或換用較小模型，強制 verifier 參與；量測修復成功率、unsafe acceptance、
  regression、execution cost；多 LLM（至少 2 個模型）；M2a 重跑 10 seeds。
- **P2**：service-level constraints 定義表、EV/comfort 完整報告、失效注入
  逐故障影響、統計規格文字。
- **P3**：文獻補充、架構圖、演算法流程、end-to-end 案例、artifact 連結/DOI。

## 4. 結論

接受「Major Revision」。審稿人的核心問題——"What has the LLM agent actually
demonstrated that a conventional repair + deterministic validation pipeline
cannot?"——在現有 PDF 中確實無法回答；這正是 P1 hostile-proposer 實驗要補的
證據。能源基準與失效注入改列為驗證環境（審稿人建議的單主線重構），P2P 制度
結果（新數據）作為環境的定價維度證據。修改後的論文將以單一主線
「physics-grounded verification of LLM-generated controller repairs」重投。
