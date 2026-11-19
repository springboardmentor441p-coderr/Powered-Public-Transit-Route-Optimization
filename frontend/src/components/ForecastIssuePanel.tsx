import React from "react";
import { fmtInt, NOT_AVAILABLE, ReplayState } from "../api";

interface ForecastIssuePanelProps {
  inReplay: boolean;
  state: ReplayState | null;
  route: string;
  onStartReplay: () => void;
  onUseInScenario: (route: string, date: string) => void;
}

const Tile: React.FC<{ label: string; value: string; note: string; tone?: string }> = ({ label, value, note, tone }) => (
  <div className="rounded-lg border border-slate-200 p-3">
    <div className="text-[11px] font-medium text-slate-500">{label}</div>
    <div className={`mt-1 text-2xl font-bold ${tone ?? "text-slate-900"}`}>{value}</div>
    <div className="mt-0.5 text-[11px] text-slate-500">{note}</div>
  </div>
);

export const ForecastIssuePanel: React.FC<ForecastIssuePanelProps> = ({
  inReplay,
  state,
  route,
  onStartReplay,
  onUseInScenario,
}) => {
  const rd = state?.route_detail;
  const pol = state?.information_policy;
  const day = rd?.current_day;
  const daily = rd?.daily.find((d) => d.date === day);
  const ready = inReplay && state && rd && rd.route === route && day;

  return (
    <section className="rounded-xl border border-blue-200 bg-white p-5 shadow-sm" data-testid="forecast-issue-panel">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Dated forecast for the selected route</h2>
          <p className="text-xs text-slate-600">
            In replay mode the frozen model issues a forecast at 00:00 on each virtual date, using only boardings the
            reporting delay allows.
          </p>
        </div>
        <span className="w-fit rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-800">
          Predicted boardings (experimental)
        </span>
      </div>

      {!inReplay ? (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
          <span>Forecasts are issued inside a replay session. Switch to historical replay to see one for {route}.</span>
          <button
            type="button"
            onClick={onStartReplay}
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
          >
            Switch to historical replay
          </button>
        </div>
      ) : !ready ? (
        <p className="mt-4 text-sm text-slate-500">Loading the replay forecast for {route}...</p>
      ) : (
        <>
          <h3 className="mt-4 text-lg font-bold text-slate-900">
            {route} · {day}
          </h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Tile
              label="Predicted daily boardings"
              value={daily ? fmtInt(daily.forecast_boardings) : NOT_AVAILABLE}
              note="Both directions combined"
              tone="text-blue-700"
            />
            <Tile
              label="Scheduled departures"
              value={daily?.scheduled_departures != null ? fmtInt(daily.scheduled_departures) : NOT_AVAILABLE}
              note={`From GTFS ${pol?.schedule_snapshot.split(" ")[1] ?? ""}, known at issue time`}
            />
            <Tile
              label="Recorded boardings"
              value={daily?.actual_boardings != null ? fmtInt(daily.actual_boardings) : "Not released yet"}
              note={
                daily?.actual_boardings != null
                  ? "Released after the reporting delay"
                  : `Released on ${addDays(day, pol?.delay_days ?? 1)}`
              }
              tone={daily?.actual_boardings != null ? "text-slate-900" : "text-slate-400"}
            />
            <Tile
              label="Boardings history used through"
              value={pol?.latest_ridership_date_used ?? NOT_AVAILABLE}
              note={`${pol?.delay_days ?? NOT_AVAILABLE}-day reporting delay (assumed)`}
            />
          </div>
          <p className="mt-2 text-[11px] text-slate-500">
            Experimental daily total built from hourly forecasts. It counts boardings only; it does not say how full buses
            are or split demand by direction.
          </p>
          <details className="mt-3 rounded-lg border border-slate-200 p-3 text-xs text-slate-700">
            <summary className="cursor-pointer font-semibold text-slate-900">Sources, coverage and assumptions</summary>
            <ul className="mt-2 list-disc space-y-1 pl-4">
              <li>Issued: {pol?.issue_time}</li>
              <li>Covers: {pol?.horizon}</li>
              <li>Model: {pol?.model_version}</li>
              <li>Schedule: {pol?.schedule_snapshot}</li>
              <li>Route-hours forecast: {daily ? fmtInt(daily.hours) : NOT_AVAILABLE}</li>
              <li>Replay session: {state?.session.session_id}</li>
              <li>{pol?.note}</li>
            </ul>
          </details>
          <button
            type="button"
            onClick={() => onUseInScenario(route, day)}
            className="mt-4 rounded-lg bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-800"
          >
            Use this forecast in a scenario
          </button>
          {(pol?.delay_days ?? 1) > 7 ? (
            <p className="mt-1 text-[11px] text-amber-800">
              Scenarios use the saved October forecast, which assumes every past week is known. With a{" "}
              {pol?.delay_days}-day delay this replay's numbers are lower in quality and will differ.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
};

function addDays(d: string, n: number): string {
  const dt = new Date(`${d}T00:00:00Z`);
  dt.setUTCDate(dt.getUTCDate() + n);
  return dt.toISOString().slice(0, 10);
}
