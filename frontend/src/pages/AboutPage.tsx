import { MethodNote, SectionCard } from "../components/ui";

export function AboutPage() {
  return (
    <div className="space-y-6">
      <SectionCard
        title="AI_RouteRanker — Analytical Architecture & Provenance"
        subtitle="Chicago Transit Authority (CTA) Route Evaluation, Spatial Clustering & Historical Forecasting"
      >
        <div className="space-y-4 text-xs leading-relaxed text-slate-300">
          <p>
            <strong className="text-slate-100">AI_RouteRanker</strong> integrates multi-year CTA daily ridership records
            (DuckDB <code>analytical.daily_ridership</code>, 2024-01-01 through 2026-08-31) with GTFS structural network
            topology, spatial DBSCAN hub detection, directional corridor co-routing, and multi-track route rankings.
          </p>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>Stage 1 (Routes &amp; Rankings):</strong> 125 bus routes and 8 rail lines evaluated across Track 1
              (Bus), Track 2 (Rail, demand pillar 0.0), and Track 3 (Unified structural comparison).
            </li>
            <li>
              <strong>Stage 2A (Historical Ridership):</strong> Read-only DuckDB daily and monthly bus ridership queries.
              Zero-ridership days are preserved; missing dates are never fabricated.
            </li>
            <li>
              <strong>Stage 2B (Spatial Hubs):</strong> Phase 6.1 DBSCAN clustering and Top-100 hub rankings (Configs A,
              B, and C) using stop-level demand attribution proxies.
            </li>
            <li>
              <strong>Stage 2C (Corridor Topology):</strong> Phase 6.2/6.3 buffer overlap, Fréchet clustering, stop
              Jaccard similarity, and shared consecutive stop sequences kept strictly separate.
            </li>
            <li>
              <strong>Stage 2D (Historical Model Evaluation):</strong> Verified Random Forest validation, test, and
              August 2026 holdout predictions (`historical_evaluation_only`; future forecasting unsupported).
            </li>
          </ul>
        </div>
      </SectionCard>

      <MethodNote title="Analytical Boundaries" tone="warning">
        Daily route ridership does not measure simultaneous onboard passenger occupancy; spatial hub demand is a proxy;
        geographic clustering is not a socioeconomic equity metric; and historical Random Forest evaluations do not
        provide future-date forecasting.
      </MethodNote>
    </div>
  );
}
