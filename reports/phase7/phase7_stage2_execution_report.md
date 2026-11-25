# AI_RouteRanker — Phase 7 Stage 2: Canonical Real-Data Ranking Execution Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Stage:** 2 — Canonical Execution & Empirical Verification  
**Execution Timestamp:** 2026-11-25T16:56:55+05:30  
**Status:** COMPLETE & VERIFIED (100% PASS)

---

## 1. Executive Summary

Phase 7 Stage 2 executed the canonical real-data Multi-Criteria Decision-Making (MCDM) route ranking pipeline across the entire Chicago Transit Authority (CTA) transit network using the accepted Phase 6.3 feature master (`artifacts/ranking_features/route_ranker_feature_master.parquet`).

The execution implemented the approved multi-track architectural design:
1. **Track 1 (Bus Network Priority):** Evaluated all **125 canonical bus routes** under the balanced Profile A multi-criteria structure (Demand Pressure 35%, Service Provision 25%, Network Hubs 20%, Corridor Structure 20%). Handled specialized routes (10, 130, N5) with dynamic missing-criterion re-weighting ($90.0\%$ valid criterion weight coverage).
2. **Track 2 (Heavy Rail Operational Priority):** Evaluated all **8 CTA rail lines** across four operational supply and corridor criteria (Trips 30%, Span 20%, Headway 30%, Duplication 20%), strictly enforcing zero demand criteria to respect rail data isolation.
3. **Track 3 (Unified Operational Supply):** Evaluated all **133 transit routes** across mode-agnostic operational characteristics (Trips 35%, Span 20%, Headway 25%, Duplication 20%).

All four canonical artifacts and the summary metrics CSV were successfully produced, all mathematical invariants were satisfied to within $2.0 \times 10^{-6}$, and all 23 protected baseline assets remained 100% bit-for-bit identical.

---

## 2. Preflight Verification & System Environment

| Check Item | Parameter / Condition | Expected | Observed | Status |
| :--- | :--- | :--- | :--- | :--- |
| **System Memory** | Minimum Available RAM | $\ge 600.0\text{ MB}$ | $1,401.5\text{ MB}$ | **PASS** |
| **System Load** | Maximum Memory Load | $\le 95.0\%$ | $82.0\%$ | **PASS** |
| **Feature Master File** | Path Existence | `route_ranker_feature_master.parquet` | Found | **PASS** |
| **Feature Master Hash** | SHA-256 Digest | `c26aa49a...8937df85` | `c26aa49a...8937df85` | **PASS** |
| **Route Population** | Canonical Routes Count | 133 unique routes | 133 routes (125 bus, 8 rail) | **PASS** |
| **Rail Isolation** | Rail Demand Fields | Strictly NaN (4 columns) | 100% NaN across all 8 lines | **PASS** |
| **Specialized Headway** | Routes 10, 130, N5 Headways | Strictly NaN | 100% NaN | **PASS** |

---

## 3. Execution Results by Ranking Track

### 3.1 Track 1: Bus Network Priority (125 Routes)

- **Engine:** Hierarchical Weighted Sum Model (WSM) [Primary Production].
- **Profile:** Balanced Default (Profile A) — 7 Evaluated Criteria across 4 Pillars.
- **Score Distribution:** Mean = $0.3441$, Min = $0.0824$ (Route 165), Max = $0.6363$ (Route 151).

#### Top 10 Bus Priority Routes
| Rank | Route ID | Route Name | WSM Score | TOPSIS Score | Demand Pillar | Service Pillar | Hub Pillar | Corridor Pillar | Primary Driving Factor |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **#1** | **151** | Sheridan | **0.6363** | 0.6111 | 0.2624 | 0.1498 | 0.1062 | 0.1179 | Load Intensity (Contrib: 0.1375) |
| **#2** | **146** | Inner Lake Shore/Michigan Exp | **0.6174** | 0.6015 | 0.2227 | 0.1396 | 0.1262 | 0.1288 | Corridor Duplication (Contrib: 0.1288) |
| **#3** | **143** | Stockton/Michigan Express | **0.6019** | 0.6117 | 0.2246 | 0.1158 | 0.1160 | 0.1455 | Corridor Duplication (Contrib: 0.1455) |
| **#4** | **147** | Outer DuSable Lake Shore Exp | **0.5786** | 0.5712 | 0.2132 | 0.1235 | 0.1130 | 0.1289 | Corridor Duplication (Contrib: 0.1289) |
| **#5** | **134** | Stockton/LaSalle Express | **0.5716** | 0.5824 | 0.2127 | 0.1102 | 0.1070 | 0.1416 | Corridor Duplication (Contrib: 0.1416) |
| **#6** | **66** | Chicago | **0.5690** | 0.5044 | 0.2125 | 0.1994 | 0.0543 | 0.1028 | Scheduled Trips (Contrib: 0.0763) |
| **#7** | **4** | Cottage Grove | **0.5590** | 0.5117 | 0.2181 | 0.1873 | 0.0468 | 0.1068 | Scheduled Trips (Contrib: 0.0706) |
| **#8** | **20** | Madison | **0.5545** | 0.5020 | 0.2078 | 0.1837 | 0.0583 | 0.1047 | Scheduled Trips (Contrib: 0.0687) |
| **#9** | **3** | King Drive | **0.5463** | 0.5089 | 0.2117 | 0.1691 | 0.0478 | 0.1176 | Corridor Duplication (Contrib: 0.1176) |
| **#10** | **121** | Union/Streeterville Express | **0.5438** | 0.5670 | 0.2036 | 0.1147 | 0.0911 | 0.1345 | Corridor Duplication (Contrib: 0.1345) |

#### Bottom 5 Bus Priority Routes
| Rank | Route ID | Route Name | WSM Score | TOPSIS Score | Primary Contributing Reason |
| :---: | :---: | :--- | :---: | :---: | :--- |
| **#121** | **86** | 86th/Cottage Grove | **0.1189** | 0.1346 | Low trips (20), minimal hub overlap (0.0), low duplication |
| **#122** | **206** | Evanston Circulator | **0.1076** | 0.1990 | Limited span (11.8h), low load intensity, minimal hub overlap |
| **#123** | **54A** | North Cicero/Skokie Blvd | **0.1022** | 0.1301 | Low trips (26), low daily demand (211.5 rides), peripheral |
| **#124** | **31** | 31st | **0.0939** | 0.1213 | Very low trips (19), low daily demand (198.8 rides) |
| **#125** | **165** | West 65th | **0.0824** | 0.1045 | Lowest trips (14), lowest span (10.9h), lowest corridor overlap |

#### Specialized Routes Verification (Routes 10, 130, N5)
| Route ID | Route Name | Missing Criterion | Base Wt Coverage | Effective Headway Wt | WSM Score | Bus Rank | Explanation Status |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **10** | Museum of Science & Industry Exp | `am_headway_min` | $90.0\%$ | $0.0000$ (Re-weighted) | **0.4264** | **#28** / 125 | Fully explained with missing flag |
| **130** | Museum Campus | `am_headway_min` | $90.0\%$ | $0.0000$ (Re-weighted) | **0.3109** | **#69** / 125 | Fully explained with missing flag |
| **N5** | South Shore Night Bus | `am_headway_min` | $90.0\%$ | $0.0000$ (Re-weighted) | **0.2063** | **#94** / 125 | Fully explained with missing flag |

---

### 3.2 Track 2: Heavy Rail Operational Priority (8 Lines)

- **Engine:** Hierarchical Weighted Sum Model (WSM) [Primary Production].
- **Profile:** Rail Operational Priority — 4 Operational Criteria (Zero Demand Criteria).
- **Population:** All 8 CTA Heavy Rail Lines.

| Rank | Rail Line ID | Color / Line Name | WSM Score | TOPSIS Score | Scheduled Trips | Span (hrs) | AM Headway (min) | Corridor Duplication Index |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **Red** | Red Line | **0.8458** | 0.8999 | 424 | 25.0 | 4.88 | 0.5097 |
| **#2** | **Blue** | Blue Line | **0.8396** | 0.8968 | 412 | 25.2 | 5.22 | 0.4907 |
| **#3** | **Brn** | Brown Line | **0.6960** | 0.4320 | 180 | 25.1 | 4.79 | 0.6559 |
| **#4** | **G** | Green Line | **0.6694** | 0.4981 | 256 | 24.9 | 9.23 | 0.5517 |
| **#5** | **Org** | Orange Line | **0.6190** | 0.3335 | 144 | 24.7 | 7.00 | 0.5471 |
| **#6** | **P** | Purple Line | **0.6185** | 0.3538 | 188 | 24.1 | 7.89 | 0.5430 |
| **#7** | **Pink** | Pink Line | **0.5812** | 0.2933 | 122 | 24.8 | 8.68 | 0.5694 |
| **#8** | **Y** | Yellow Line (Skokie Swift) | **0.4588** | 0.1083 | 160 | 18.7 | 11.11 | 0.0264 |

**Key Finding:** Red Line (#1) and Blue Line (#2) exhibit near-identical high operational commitment (424 & 412 trips, 24/7 continuous span, sub-5-minute AM headways). Yellow Line (#18.7h span, 11.1 min headway, lowest corridor sharing) ranks #8.

---

### 3.3 Track 3: Unified Network Operational Supply (133 Routes)

- **Engine:** Hierarchical Weighted Sum Model (WSM) [Primary Production].
- **Profile:** Unified Operational Supply — 4 Mode-Agnostic Operational Criteria.
- **Population:** All 133 CTA Routes (125 Bus + 8 Rail).

#### Top 10 Unified Operational Supply Routes
| Rank | Route ID | Route Short Name | Mode | WSM Score | TOPSIS Score | Scheduled Trips | Service Span (hrs) | AM Headway (min) | Corridor Duplication |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **Red** | Red Line | Rail | **0.8458** | 0.7915 | 424 | 24.97 h | 4.93 m | 0.2399 |
| **#2** | **79** | 79th | Bus | **0.8417** | 0.7965 | 457 | 24.78 h | 5.58 m | 0.2650 |
| **#3** | **Blue** | Blue Line | Rail | **0.8390** | 0.7898 | 412 | 25.22 h | 5.16 m | 0.2417 |
| **#4** | **66** | Chicago | Bus | **0.8200** | 0.7819 | 398 | 24.62 h | 5.03 m | 0.2343 |
| **#5** | **20** | Madison | Bus | **0.7763** | 0.7678 | 346 | 24.42 h | 6.34 m | 0.3259 |
| **#6** | **9** | Ashland | Bus | **0.7749** | 0.7513 | 335 | 25.08 h | 9.77 m | 0.5031 |
| **#7** | **4** | Cottage Grove | Bus | **0.7321** | 0.6935 | 248 | 24.88 h | 9.71 m | 0.6797 |
| **#8** | **49** | Western | Bus | **0.7268** | 0.7423 | 269 | 25.00 h | 9.89 m | 0.5626 |
| **#9** | **77** | Belmont | Bus | **0.7193** | 0.7303 | 329 | 24.60 h | 7.08 m | 0.1418 |
| **#10** | **53** | Pulaski | Bus | **0.7094** | 0.7258 | 304 | 25.14 h | 8.76 m | 0.2550 |

**Key Finding:** Route 79 demonstrates operational supply characteristics comparable to major CTA rail lines across the selected scheduled-trip, service-span and AM-headway indicators. While bus and heavy rail operations have distinct physical vehicle capacities, passenger carrying volumes, and right-of-way characteristics (such that bus and rail scheduling metrics are not claimed to be perfectly equivalent), Route 79's 457 scheduled trips, 24.78-hour continuous owl service span, and 5.58-minute AM peak headway reflect an intensive operational commitment that places it among the highest-frequency transit corridors in Chicago. Heavy trunk bus lines such as Route 66 (#4, 398 trips, 5.03m headway) and Route 20 (#5, 346 trips, 6.34m headway) likewise exhibit high operational supply.

---

## 4. Methodological Benchmark: WSM vs TOPSIS Comparison

As approved in the Phase 7 architecture and audit closure, TOPSIS was executed as an exploratory benchmark on common complete-case populations to ensure rigorous metric comparability.

| Evaluation Track | Benchmark Population | Population Size ($N$) | Spearman Rank Correlation ($\rho$) | Top-10 Overlap | Top-20 Overlap | Alignment Assessment |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Track 1: Bus Priority** | Complete Cases Only | $N = 122$ | **$0.9768$** | $70.0\%$ | $85.0\%$ | Extremely High Rank Concordance |
| **Track 2: Rail Priority** | All Rail Lines | $N = 8$ | **$0.9524$** | $100.0\%$ (Top-8) | N/A | Extremely High Rank Concordance |
| **Track 3: Unified Supply**| Complete Cases Only | $N = 130$ | **$0.9938$** | $100.0\%$ | $85.0\%$ | Near-Perfect Concordance |

---

## 5. Sensitivity Analysis Summary

A one-at-a-time (OAT) parameter sensitivity analysis was executed across 60 distinct weight perturbation scenarios ($\pm 10\%$ and $\pm 20\%$ for each criterion within each track/profile).

- **Bus Network Priority Stability:** Mean Spearman $\rho = 0.9989$, with minimum $\rho = 0.9935$ under a $-20\%$ shift in Load Intensity.
- **Rail Operational Priority Stability:** Mean Spearman $\rho = 0.9881$, with minimum $\rho = 0.9524$ under extreme headway variations.
- **Unified Operational Supply Stability:** Mean Spearman $\rho = 0.9984$, with minimum $\rho = 0.9942$.
- **Conclusion:** The ranking orders are remarkably robust against local weight fluctuations.

---

## 6. Generated Canonical Artifacts Inventory

| Artifact Name | Relative File Path | Record / Row Count | File Size (Bytes) | SHA-256 Digest |
| :--- | :--- | :---: | :---: | :--- |
| **Master Rankings Parquet** | `artifacts/ranking_results/route_rankings_master.parquet` | 266 records | 103,565 | `c440671d0b3888683969cb5fc11ccf7b581128a7296069019f76202b64f0093b` |
| **Route Explanations JSON** | `artifacts/ranking_results/route_ranking_explanations.json` | 266 explanations | 797,352 | `56c29ef9c77b7517e8cb621a207600aa576148aef015a35a364da029a74a24b2` |
| **Sensitivity Analysis Parquet**| `artifacts/ranking_results/ranking_sensitivity_analysis.parquet` | 60 scenarios | 7,522 | `fb41bcdf1e18da7978ae1666535d5868a92467143bd3d08b7ee5d71ef5d6790c` |
| **Phase 7 Metadata JSON** | `artifacts/ranking_results/phase7_metadata.json` | Key-value store | 1,963 | `f29799139e4a861ea4f8b3679f96fa3e022436904b3c52fc8b7fc5a1cfd9ceca` |
| **Metrics Summary CSV** | `reports/phase7/phase7_stage2_metrics_summary.csv` | 125 bus rows | 25,349 | `2475e399d2b53ebc7d6e1cb4d7eba19beb91924198620446e4fe2138fc88956f` |

---

## 7. Protected Assets Verification

All 23 baseline protected assets were verified via SHA-256 immediately following pipeline completion. All 23 digests match their authoritative baseline values with zero modifications.
