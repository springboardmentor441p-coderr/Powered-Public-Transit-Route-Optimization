# Delivery status

The selected scope is one defensible New York bus network. The product is a planning decision-support prototype with historical evidence and explicit scenario assumptions.

| Area | Current evidence |
|---|---|
| Collection through EDA | Executed notebooks01?04, versioned sources and matched route/date products |
| Forecasting | Notebooks05?08 and12?13, chronological baselines, regression/Random Forest comparisons and saved pipelines |
| Groups and review | Notebooks09?10, interpretable profiles, exploratory clustering and named indicators |
| Scenarios | Notebook11, saved individual route/date scenarios, forecast linkage, zero-service handling and assumptions |
| Application | React/TypeScript maps, route selection, history, comparisons, ranking, forecasts, replay and scenarios |
| API and persistence | FastAPI and PostgreSQL, immutable model/forecast identity, controlled reveal and retained reset history |
| Verification | 123 tests passed; eight-screen browser journey and separate map/scenario UI checks |
| Deployment | React/API/PostgreSQL container configuration prepared; Docker execution remains unverified |

Adding schedule features did not beat the seasonal baseline on the paired retrospective test population. That candidate was not promoted. The current replay model remains experimental; prospective acceptance and interval evaluation are separate gates.

Geometry and profile versions unavailable at the replay clock are withheld. Daily observations combine both directions; they cannot establish simultaneous occupancy or direction-specific demand. Driver duties, fleet feasibility, actual running-time optimization, equity/accessibility outcomes and measured intervention benefits require further data and validation.

Earlier Streamlit, optional observed-label intake and allocation experiments are preserved. Observed overcrowding labels, 23-city coverage and a full fleet/crew solver are not prerequisites for the selected prototype.

See APPLICATION.md, API_CONTRACT.md and ACCEPTANCE.md for commands, contracts and current verification evidence. Source data, private files, runtime records and generated handoff packages remain local and excluded from Git.
