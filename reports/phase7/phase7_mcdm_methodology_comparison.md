# Phase 7 — MCDM Methodology Comparison Report
## Comparative Evaluation of Multi-Criteria Decision-Making Frameworks

**Project:** `AI_RouteRanker — AI-Powered Public Transit Route Optimization`  
**Root Path:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** Milestone 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Phase:** 7 — Requirements Discovery and Architecture Planning  
**Status:** COMPLETE / METHODOLOGY RECOMMENDATION BASELINE  

---

## 1. Executive Summary

A core objective of Milestone 7 is to select a mathematically sound, computationally efficient, robust, and highly explainable **Multi-Criteria Decision-Making (MCDM)** methodology to evaluate the 133 transit routes of the Chicago Transit Authority (CTA).

This report conducts a rigorous comparative assessment of five prominent MCDM methodologies:
1. **Weighted Sum Model (WSM) / Simple Additive Weighting (SAW)**
2. **Technique for Order Preference by Similarity to Ideal Solution (TOPSIS)**
3. **Analytic Hierarchy Process (AHP)**
4. **VIKOR (ViseKriterijumska Optimizacija I Kompromisno Resenje)**
5. **Outranking Methods (PROMETHEE II / ELECTRE III)**

### Core Recommendation:
- **Primary Operational Engine:** **Hierarchical Weighted Sum Model (WSM)** with dynamic criterion weight masking.
- **Secondary Benchmark & Validation Engine:** **TOPSIS** with Euclidean distance to ideal and anti-ideal reference points.
- **Role of Hybrid Architecture:** WSM serves as the authoritative, production-facing engine because of its strict linear additivity, complete explainability, absence of rank reversal under alternative additions, and clean handling of missing criteria via dynamic weight renormalization. TOPSIS is integrated as an automated, secondary sensitivity benchmark to evaluate whether non-linear distance trade-offs identify divergent outlier routes.

---

## 2. Theoretical Overview of Candidate MCDM Frameworks

### 2.1 Weighted Sum Model (WSM / SAW)
- **Mathematical Formulation:**
  For alternative $r \in \{1, \dots, N\}$ and criteria $i \in \{1, \dots, M\}$ with weights $w_i \ge 0, \sum w_i = 1$:
  $$S_{\text{WSM}}(r) = \sum_{i=1}^{M} w_i \cdot x_{r, i}$$
  where $x_{r, i} \in [0, 1]$ is the normalized criterion value.
- **Key Characteristics:**
  - Evaluates utility through strict linear combination.
  - Transparent trade-offs: a loss of $\Delta$ on criterion $i$ can be compensated by an increase of $(\Delta \cdot w_i / w_j)$ on criterion $j$.
  - Exact additive contribution: each criterion's contribution to the total score is precisely $C_{r, i} = w_i \cdot x_{r, i}$.

### 2.2 Technique for Order Preference by Similarity to Ideal Solution (TOPSIS)
- **Mathematical Formulation:**
  Constructs a positive ideal solution (PIS, $A^+$) and negative ideal solution (NIS, $A^-$):
  $$v_{r, i} = w_i \cdot x_{r, i}$$
  $$A^+ = \{v_1^+, \dots, v_M^+\} = \{\max_r v_{r, i} \mid i \in B, \min_r v_{r, i} \mid i \in C\}$$
  $$A^- = \{v_1^-, \dots, v_M^-\} = \{\min_r v_{r, i} \mid i \in B, \max_r v_{r, i} \mid i \in C\}$$
  Computes Euclidean separation distances $D_r^+$ and $D_r^-$:
  $$D_r^+ = \sqrt{\sum_{i=1}^M (v_{r, i} - v_i^+)^2}, \quad D_r^- = \sqrt{\sum_{i=1}^M (v_{r, i} - v_i^-)^2}$$
  Calculates relative closeness to the ideal solution:
  $$C_r = \frac{D_r^-}{D_r^+ + D_r^-} \in [0, 1]$$
- **Key Characteristics:**
  - Chooses the alternative simultaneously closest to the best possible hypothetical route and farthest from the worst.
  - Accounts for geometric trade-offs in multidimensional Euclidean space.

### 2.3 Analytic Hierarchy Process (AHP)
- **Mathematical Formulation:**
  Decomposes decision criteria into a hierarchical tree. Derives criterion weights from expert pairwise comparison matrices $A = [a_{ij}]$ via the principal eigenvector:
  $$A w = \lambda_{\max} w$$
  Computes a Consistency Ratio ($CR = CI / RI < 0.10$) to validate transitivity of human judgments.
- **Key Characteristics:**
  - Excellent for deriving criteria weights from expert interviews.
  - Cumbersome and prone to judgment inconsistency when evaluating large numbers of alternatives ($N = 133$). Evaluating $133 \times 133$ pairwise matrices directly is computationally prohibitive ($8,778$ comparisons per criterion).

### 2.4 VIKOR (Multi-Criteria Optimization and Compromise Solution)
- **Mathematical Formulation:**
  Determines a compromise ranking based on mutual concession, optimizing both group utility ($S_r$, Manhattan distance) and individual regret ($R_r$, Chebyshev distance):
  $$S_r = \sum_{i=1}^M w_i \frac{f_i^* - x_{r, i}}{f_i^* - f_i^-}, \quad R_r = \max_i \left( w_i \frac{f_i^* - x_{r, i}}{f_i^* - f_i^-} \right)$$
  Computes aggregate index $Q_r = v \frac{S_r - S^*}{S^- - S^*} + (1 - v) \frac{R_r - R^*}{R^- - R^*}$.
- **Key Characteristics:**
  - Focuses on resolving conflicting criteria in competitive negotiations.
  - Sensitive to the choice of consensus weight $v$ (typically $0.5$). Less intuitive for public transit service analysis where individual regret metrics do not correspond to physical transit operational concepts.

### 2.5 Outranking Methods (PROMETHEE II / ELECTRE III)
- **Mathematical Formulation:**
  Conducts pairwise comparisons between all alternative pairs $(a, b)$ using preference thresholds (indifference $q$, strict preference $p$, veto $v$). Constructs net outranking flows $\Phi(a) = \Phi^+(a) - \Phi^-(a)$.
- **Key Characteristics:**
  - Eliminates the need for artificial linear compensation.
  - Highly complex parameterization: requires configuring multiple threshold parameters for each criterion.
  - Pairwise complexity is $O(N^2 \cdot M)$. For $133$ routes, requires $17,556$ pairwise evaluations per run.
  - Generates opaque, non-additive flow values that cannot be broken down into clean visual waterfall charts for transit planners.

---

## 3. Systematic Methodology Comparison Matrix

| Evaluation Dimension | Weighted Sum Model (WSM) | TOPSIS | Analytic Hierarchy Process (AHP) | VIKOR | PROMETHEE / ELECTRE |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Computational Complexity** | $O(N \cdot M)$ — Extremely Fast | $O(N \cdot M)$ — Fast | $O(N^2 \cdot M)$ or $O(M^2)$ | $O(N \cdot M)$ — Fast | $O(N^2 \cdot M)$ — Intensive |
| **Mathematical Transparency** | Direct linear utility ($\sum w_i x_i$) | Euclidean geometric distance | Eigenvalue pairwise synthesis | Chebyshev & Manhattan metric | Outranking concordance flows |
| **Additive Explainability for UI** | **100% Additive** ($Score = \sum C_i$) | Non-additive non-linear root | Additive utility over weights | Non-additive min/max blend | Non-additive net flows |
| **Missing-Data Resilience** | **High** (Dynamic weight masking) | Moderate (Distorts ideal points) | Low (Breaks pairwise matrix) | Low (Distorts regret bound) | Poor (Breaks pairwise threshold) |
| **Susceptibility to Rank Reversal** | **Zero** (Independent evaluations) | Known risk when routes added | Known risk upon alternative shifts | Known risk | High risk |
| **Transit Planning Intuitiveness** | **Very High** (Clear point scoring) | High (Ideal benchmark concept) | Moderate | Moderate | Low (Abstract net flows) |
| **Suitability for AI_RouteRanker** | **Primary Choice (10/10)** | **Benchmark Choice (8/10)** | Weight Elicitation Only (5/10) | Secondary Alternative (6/10) | Unsuitable for Project (3/10) |

---

## 4. Deep-Dive: Why Weighted Sum Model (WSM) is the Optimal Primary Engine

### 4.1 Perfect Additive Explainability for Frontend Visualization
A transit planner using the AI_RouteRanker interactive dashboard needs to see exactly why Route 79 received an overall score of $0.842$:
$$\text{Score}(79) = \underbrace{0.182}_{\text{Load Intensity}} + \underbrace{0.145}_{\text{Demand}} + \underbrace{0.095}_{\text{Headway}} + \underbrace{0.088}_{\text{Trips}} + \underbrace{0.078}_{\text{Duplication}} + \dots$$
Under WSM, every single point in the composite score is directly attributable to a physical transit criterion. This enables:
- Interactive **waterfall charts** showing positive and negative score components.
- Intuitive **radar charts** broken down by planning pillars.
- Plain-English automated narrative synthesis that directly reflects the numerical calculations.

Under geometric methods (TOPSIS) or outranking flows (PROMETHEE), an alternative's score depends non-linearly on the square root of sum of squared differences across all dimensions. If a route's demand increases, its distance changes non-linearly, making it impossible to produce a true additive breakdown.

### 4.2 Seamless Missing-Data Handling via Dynamic Weight Masking
As documented in the requirements discovery report:
- 8 rail routes miss all demand criteria.
- 3 specialized bus routes miss AM headways.

Under WSM, missing values are resolved through **exact dynamic weight renormalization**:
$$S_{\text{WSM}}(r) = \sum_{i \in \text{Valid}(r)} \left( \frac{w_i}{\sum_{j \in \text{Valid}(r)} w_j} \right) x_{r, i}$$
This preserves the relative trade-off ratios between the remaining valid criteria without introducing artificial imputation bias.

In contrast, under TOPSIS, if an alternative has `NaN` for a criterion, computing the Euclidean distance $\sqrt{\sum (v_i - v_i^+)^2}$ fails unless missing values are imputed. Imputing with column means artificially clusters the route toward the center of the solution space, distorting the distances of all other alternatives.

### 4.3 Immunity to Rank Reversal
A widely acknowledged flaw of distance-to-ideal and outranking methods is **rank reversal**: introducing or removing an irrelevant alternative can alter the relative rank order of other unchanged alternatives because the ideal points ($A^+, A^-$) or pairwise dominance flows shift.

WSM is mathematically immune to rank reversal. The score of Route A depends solely on its own attributes and the fixed criterion weights, completely independent of whether Route B is present in the dataset.

---

## 5. The Role of TOPSIS as a Secondary Benchmark

While WSM is selected as the primary user-facing engine, TOPSIS provides immense analytical value as an independent, secondary verification engine:

1. **Detection of Compromise Outliers:** TOPSIS penalizes alternatives with unbalanced, extreme profiles (e.g., extremely high demand but catastrophically poor headway) more heavily than WSM due to the quadratic nature of Euclidean distance.
2. **Methodological Cross-Validation:** Computing Spearman's rank correlation ($\rho$) between WSM and TOPSIS rankings serves as a rigorous stability check. A correlation $\rho > 0.90$ proves that the ranking is robust to the underlying mathematical formulation and not an artifact of linear weighting.

---

## 6. Conclusion & Selection Decision

The decision for Phase 7 implementation is formally established:
- **Primary Method:** **Hierarchical Weighted Sum Model (WSM)** with dynamic criterion weight masking.
- **Secondary / Sensitivity Method:** **TOPSIS**, executed on identical normalized inputs to compute comparative correlation metrics and identify non-linear trade-off outliers.

We proceed to formulate the specific criteria, weights, and mathematical transformations in `reports/phase7/phase7_criteria_and_weight_design.md`.
