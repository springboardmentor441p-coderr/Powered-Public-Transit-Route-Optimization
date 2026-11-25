import { useState, type ReactNode } from "react";
import {
  Activity,
  BarChart3,
  Compass,
  GitBranch,
  Info,
  LayoutDashboard,
  MapPin,
  Menu,
  Route as RouteIcon,
  TrendingUp,
  Trophy,
  X,
} from "lucide-react";
import type { HealthCheckResponse } from "../types/api";

export type NavSectionId =
  | "overview"
  | "routes"
  | "rankings"
  | "ridership"
  | "spatial"
  | "corridors"
  | "forecasting"
  | "about";

export const NAV_ITEMS: Array<{
  id: NavSectionId;
  label: string;
  subtitle: string;
  icon: typeof LayoutDashboard;
}> = [
  { id: "overview", label: "Overview", subtitle: "System-wide analytical summary", icon: LayoutDashboard },
  { id: "routes", label: "Routes", subtitle: "133 canonical bus & rail profiles", icon: RouteIcon },
  { id: "rankings", label: "Route Rankings", subtitle: "Multi-track scores, explanations & sensitivity", icon: Trophy },
  { id: "ridership", label: "Ridership Analytics", subtitle: "Historical CTA bus ridership (2024–2026)", icon: TrendingUp },
  { id: "spatial", label: "Spatial Hubs", subtitle: "DBSCAN clusters & top-100 hub map", icon: MapPin },
  { id: "corridors", label: "Corridor Analysis", subtitle: "Overlap, Jaccard & co-routing sequences", icon: GitBranch },
  { id: "forecasting", label: "Historical Model Eval", subtitle: "Random Forest validation, test & holdout", icon: BarChart3 },
  { id: "about", label: "About Project", subtitle: "Methodology, provenance & scope", icon: Info },
];

export function Layout({
  activeSection,
  onNavigate,
  health,
  healthError,
  children,
}: {
  activeSection: NavSectionId;
  onNavigate: (id: NavSectionId) => void;
  health: HealthCheckResponse | null;
  healthError: string | null;
  children: ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const current = NAV_ITEMS.find((n) => n.id === activeSection) ?? NAV_ITEMS[0];

  const handleSelect = (id: NavSectionId) => {
    onNavigate(id);
    setMobileOpen(false);
  };

  const navContent = (
    <nav aria-label="Primary Navigation" className="flex flex-1 flex-col gap-1 px-3 py-4">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const active = item.id === activeSection;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => handleSelect(item.id)}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors ${
              active
                ? "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/40"
                : "text-slate-300 hover:bg-slate-800/80 hover:text-slate-100"
            }`}
          >
            <Icon className={`h-4 w-4 shrink-0 ${active ? "text-sky-400" : "text-slate-400"}`} />
            <span className="truncate">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Desktop Sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-900/80 lg:flex">
        <div className="flex items-center gap-2.5 border-b border-slate-800 px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/40">
            <Compass className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-bold tracking-tight text-slate-50">AI_RouteRanker</p>
            <p className="text-[11px] text-slate-400">Transit Analytics v{health?.version ?? "0.1.0"}</p>
          </div>
        </div>
        {navContent}
        <div className="border-t border-slate-800 p-4 text-[11px] text-slate-400">
          Read-only historical &amp; GTFS analytical API integration.
        </div>
      </aside>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-slate-950/75 backdrop-blur-xs"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative z-10 flex w-72 max-w-[85vw] flex-col border-r border-slate-800 bg-slate-900">
            <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3.5">
              <span className="text-sm font-bold text-slate-50">AI_RouteRanker</span>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation menu"
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            {navContent}
          </aside>
        </div>
      )}

      {/* Main Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/90 px-4 py-3 backdrop-blur-md sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation menu"
              className="rounded-lg border border-slate-800 bg-slate-900 p-2 text-slate-300 hover:bg-slate-800 lg:hidden"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-base font-bold text-slate-50 sm:text-lg">{current.label}</h1>
              <p className="truncate text-xs text-slate-400">{current.subtitle}</p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
                health
                  ? "border-emerald-500/40 bg-emerald-950/50 text-emerald-300"
                  : "border-rose-500/40 bg-rose-950/50 text-rose-300"
              }`}
              title={health ? `Connected (${health.environment})` : healthError ?? "Disconnected"}
            >
              <Activity className="h-3.5 w-3.5" />
              <span>{health ? "API Online" : "API Offline"}</span>
            </span>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
