import React from "react";

interface PageHeaderProps {
  title: string;
  subtitle: string;
  period: string;
  source: string;
  rightSlot?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  period,
  source,
  rightSlot,
}) => {
  return (
    <div className="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">{title}</h1>
          <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
        </div>
        {rightSlot ? <div className="shrink-0">{rightSlot}</div> : null}
      </div>
      <div className="mt-4 flex flex-wrap gap-3 border-t border-slate-100 pt-3 text-xs text-slate-600">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
          <span className="font-semibold text-slate-900">Period:</span> {period}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2.5 py-1 font-medium text-blue-800">
          <span className="font-semibold text-blue-950">Source:</span> {source}
        </span>
      </div>
    </div>
  );
};

