"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

export default function AutoRefresh({ seconds = 5 }: { seconds?: number }) {
  const router = useRouter();
  const [enabled, setEnabled] = useState(true);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => {
      startTransition(() => {
        router.refresh();
      });
    }, seconds * 1000);
    return () => clearInterval(id);
  }, [router, seconds, enabled]);

  function handleManualRefresh() {
    startTransition(() => {
      router.refresh();
    });
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs text-slate-600">
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            enabled ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
          }`}
        />
        <span className="font-medium">{enabled ? `Live (${seconds}s)` : "Paused"}</span>
      </div>

      <button
        onClick={() => setEnabled((prev) => !prev)}
        title={enabled ? "Pause live auto-refresh" : "Resume live auto-refresh"}
        className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors cursor-pointer"
      >
        {enabled ? "Pause" : "Resume"}
      </button>

      <button
        onClick={handleManualRefresh}
        disabled={isPending}
        title="Refresh data now"
        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors disabled:opacity-50 cursor-pointer"
      >
        <svg
          className={`w-3.5 h-3.5 text-slate-500 ${isPending ? "animate-spin" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
          />
        </svg>
        <span>Refresh</span>
      </button>
    </div>
  );
}
