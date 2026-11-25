import type { ApiKey, UsageRow, Worker } from "@/lib/gateway";

function formatNumber(num: number): string {
  return new Intl.NumberFormat("en-US").format(num);
}

export default function MetricsOverview({
  workers,
  keys,
  usage,
}: {
  workers: Worker[];
  keys: ApiKey[];
  usage: UsageRow[];
}) {
  const totalInflight = workers.reduce((acc, w) => acc + (w.inflight || 0), 0);
  const totalConcurrency = workers.reduce((acc, w) => acc + (w.max_concurrency || 0), 0);
  const activeKeysCount = keys.filter((k) => k.revoked_at === null).length;
  const totalTokens = usage.reduce(
    (acc, u) => acc + (u.prompt_tokens || 0) + (u.completion_tokens || 0),
    0
  );
  const totalRequests = usage.reduce((acc, u) => acc + (u.requests || 0), 0);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Active Workers Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase tracking-wider">
          <span>GPU Workers</span>
          <span className="p-1 rounded bg-slate-50 text-slate-700">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.75"
                d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"
              />
            </svg>
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-slate-900">
            {workers.length}
          </span>
          <span className="text-xs text-slate-500">
            online {totalConcurrency > 0 ? `(${totalConcurrency} max slots)` : ""}
          </span>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {workers.length > 0 ? "Outbound WebSocket clusters active" : "Waiting for worker registration"}
        </p>
      </div>

      {/* In-Flight Inferences Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase tracking-wider">
          <span>In-Flight Load</span>
          <span className="p-1 rounded bg-slate-50 text-slate-700">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.75"
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
            {totalInflight}
          </span>
          <span className="text-xs text-slate-500">concurrent requests</span>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Real-time backpressure telemetry
        </p>
      </div>

      {/* Active API Keys Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase tracking-wider">
          <span>Active API Keys</span>
          <span className="p-1 rounded bg-slate-50 text-slate-700">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.75"
                d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
              />
            </svg>
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
            {activeKeysCount}
          </span>
          <span className="text-xs text-slate-500">
            of {keys.length} total
          </span>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Hashed at rest with rate limits
        </p>
      </div>

      {/* Metered Tokens Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase tracking-wider">
          <span>Tokens Metered</span>
          <span className="p-1 rounded bg-slate-50 text-slate-700">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.75"
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
          </span>
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
            {formatNumber(totalTokens)}
          </span>
          <span className="text-xs text-slate-500">tokens</span>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Across {formatNumber(totalRequests)} completed requests
        </p>
      </div>
    </div>
  );
}
