import React from "react";
import {
  DAY_TYPES,
  OBS_END,
  OBS_START,
  ReplayState,
  RouteSummary,
} from "../api";

export type AppMode = "historical" | "replay";

export interface ViewContext {
  mode: AppMode;
  route: string;
  start: string;
  end: string;
  dayType: string; // "all" | one of DAY_TYPES
}

export const DEFAULT_CONTEXT: ViewContext = {
  mode: "historical",
  route: "M15+",
  start: OBS_START,
  end: OBS_END,
  dayType: "all",
};

interface ContextBarProps {
  ctx: ViewContext;
  routes: RouteSummary[];
  onChange: (next: ViewContext) => void;
}

export const ContextBar: React.FC<ContextBarProps> = ({ ctx, routes, onChange }) => {
  const set = (patch: Partial<ViewContext>) => onChange({ ...ctx, ...patch });
  const fieldCls =
    "rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-900";

  return (
    <div className="border-b border-slate-200 bg-slate-50" data-testid="context-bar">
      <div className="mx-auto flex max-w-7xl flex-wrap items-end gap-x-4 gap-y-2 px-4 py-2 sm:px-6">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Mode</span>
          <div className="inline-flex rounded-md border border-slate-300 bg-white p-0.5" role="group" aria-label="Data mode">
            {(
              [
                ["historical", "Historical observations"],
                ["replay", "Historical replay"],
              ] as Array<[ViewContext["mode"], string]>
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                aria-pressed={ctx.mode === id}
                onClick={() => set({ mode: id })}
                className={`rounded px-2.5 py-1 text-xs font-semibold transition ${
                  ctx.mode === id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Route</span>
          <select
            aria-label="Selected route"
            value={ctx.route}
            onChange={(e) => set({ route: e.target.value })}
            className={fieldCls}
          >
            {routes.map((r) => (
              <option key={r.route} value={r.route}>
                {r.route} · {r.route_long_name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">From</span>
          <input
            type="date"
            aria-label="From date"
            min={OBS_START}
            max={ctx.end}
            value={ctx.start}
            onChange={(e) => e.target.value && set({ start: e.target.value })}
            className={fieldCls}
          />
        </label>

        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Through</span>
          <input
            type="date"
            aria-label="Through date"
            min={ctx.start}
            max={OBS_END}
            value={ctx.end}
            onChange={(e) => e.target.value && set({ end: e.target.value })}
            className={fieldCls}
          />
        </label>

        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Day type</span>
          <select
            aria-label="Day type"
            value={ctx.dayType}
            onChange={(e) => set({ dayType: e.target.value })}
            className={fieldCls}
          >
            <option value="all">All typical days</option>
            {DAY_TYPES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          onClick={() => onChange({ ...DEFAULT_CONTEXT, route: ctx.route, mode: ctx.mode })}
          className="rounded-md px-2 py-1 text-xs font-medium text-slate-500 underline-offset-2 hover:text-slate-900 hover:underline"
        >
          Reset dates
        </button>

        <p className="ml-auto max-w-sm text-[11px] leading-snug text-slate-500">
          Recorded data covers {OBS_START} to {OBS_END} (typical days only). Filters apply to route detail,
          comparison and ranking screens.
        </p>
      </div>
    </div>
  );
};

interface ReplayBannerProps {
  state: ReplayState | null;
  busy: boolean;
  error: string | null;
  onControl: (action: "start" | "pause" | "advance") => void;
  onOpen: () => void;
}

export const ReplayBanner: React.FC<ReplayBannerProps> = ({ state, busy, error, onControl, onOpen }) => {
  const status = state?.session.status;
  return (
    <div className="border-b border-amber-200 bg-amber-50" role="status" data-testid="replay-banner">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 text-xs text-amber-950 sm:px-6">
        <span className="rounded bg-amber-200 px-2 py-0.5 font-bold uppercase tracking-wide">Historical replay</span>
        {state ? (
          <>
            <span>
              Virtual date <strong data-testid="virtual-date">{state.virtual_date}</strong>
            </span>
            <span>
              Boardings shown through <strong>{state.information_policy.latest_revealed_date}</strong> (
              {state.information_policy.delay_days}-day reporting delay, assumed)
            </span>
            <span>
              Status <strong>{state.session.status_label ?? status}</strong>
            </span>
            <span className="text-amber-800">Not a live feed. This replays past dates.</span>
            <div className="ml-auto flex gap-1">
              {status === "playing" ? (
                <button type="button" disabled={busy} onClick={() => onControl("pause")} className="rounded border border-amber-300 bg-white px-2 py-0.5 font-semibold hover:bg-amber-100">
                  Pause
                </button>
              ) : (
                <button type="button" disabled={busy || state.completed} onClick={() => onControl("start")} className="rounded border border-amber-300 bg-white px-2 py-0.5 font-semibold hover:bg-amber-100 disabled:opacity-50">
                  Play
                </button>
              )}
              <button type="button" disabled={busy || state.completed} onClick={() => onControl("advance")} className="rounded border border-amber-300 bg-white px-2 py-0.5 font-semibold hover:bg-amber-100 disabled:opacity-50">
                Next day
              </button>
              <button type="button" onClick={onOpen} className="rounded bg-amber-900 px-2 py-0.5 font-semibold text-white hover:bg-amber-800">
                Open replay
              </button>
            </div>
          </>
        ) : (
          <span>{error ?? "Starting a replay session..."}</span>
        )}
      </div>
    </div>
  );
};

export const ProvenanceLegend: React.FC = () => (
  <footer className="mt-10 border-t border-slate-200 bg-white" data-testid="provenance-legend">
    <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-4 text-[11px] text-slate-600 sm:px-6">
      <span className="font-semibold text-slate-800">What the values are:</span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-slate-900" /> Published boardings (MTA hourly ridership)
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-slate-400" /> Scheduled service (GTFS trips and service hours)
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-blue-600" /> Predicted boardings (experimental)
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-sm bg-amber-500" /> Scenario assumptions
      </span>
      <span className="text-slate-500">Boardings count people getting on. They do not measure how full a bus is.</span>
    </div>
  </footer>
);
