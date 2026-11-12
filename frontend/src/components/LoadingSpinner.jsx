import React from 'react';
import { Loader2 } from 'lucide-react';

export default function LoadingSpinner({ message = 'Loading CTA transit data...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-400">
      <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
      <span className="text-sm font-medium">{message}</span>
    </div>
  );
}

