import { redirect } from "next/navigation";

import AutoRefresh from "@/components/auto-refresh";
import KeyManager, { type KeyRow } from "@/components/key-manager";
import MetricsOverview from "@/components/metrics-overview";
import SignOut from "@/components/sign-out";
import { loadDashboard } from "@/lib/gateway";
import { isAuthenticated } from "@/lib/session";

export const dynamic = "force-dynamic";

function formatTime(seconds: number): string {
  if (!seconds) return "—";
  return new Date(seconds * 1000).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

function percent(value: number): number {
  return Math.round((value || 0) * 100);
}

export default async function Home() {
  if (!(await isAuthenticated())) {
    redirect("/login");
  }

  const data = await loadDashboard();

  const keyRows: KeyRow[] = data.keys.map((key) => {
    const used = data.usage.find((item) => item.id === key.id);
    return {
      id: key.id,
      name: key.name,
      prefix: key.prefix,
      created: formatTime(key.created_at),
      revoked: key.revoked_at !== null,
      requests: used?.requests ?? 0,
      promptTokens: used?.prompt_tokens ?? 0,
      completionTokens: used?.completion_tokens ?? 0,
    };
  });

  const isGpuOnline = data.inference === "ok";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      {/* Top Enterprise Navigation Bar */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-sm border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          {/* Logo & Platform Info */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center text-white shadow-sm">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 15a4 4 0 004 4h10a4 4 0 004-4 4 4 0 00-4-4 7 7 0 00-13 1 4 4 0 00-1 3z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-900 tracking-tight text-base">CloudScale AI</span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                  hybrid-cloud
                </span>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">
                Distributed Inference Gateway & Control Plane
              </p>
            </div>
          </div>

          {/* Real-time Status Badges & Controls */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Gateway Status Badge */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                data.gatewayOnline
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-rose-50 text-rose-700 border-rose-200"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  data.gatewayOnline ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
                }`}
              />
              <span className="hidden md:inline">Gateway</span>
              <span>{data.gatewayOnline ? "Online" : "Unreachable"}</span>
            </div>

            {/* Inference Worker Badge */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                isGpuOnline
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${isGpuOnline ? "bg-emerald-500" : "bg-amber-500"}`} />
              <span className="hidden md:inline">Inference:</span>
              <span>{isGpuOnline ? "GPU Ready" : "Standby"}</span>
            </div>

            {/* Auto Refresh Component */}
            <div className="hidden lg:block">
              <AutoRefresh seconds={5} />
            </div>

            {/* Sign Out Button */}
            <SignOut />
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Gateway Spin-up / Error Alert */}
        {data.error && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-900 shadow-sm flex items-start gap-3">
            <svg className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="space-y-1">
              <p className="font-semibold text-amber-900">Gateway communication notice</p>
              <p className="text-amber-800 text-xs sm:text-sm">
                {data.error}. If the control plane is hosted on a free cloud instance (e.g., Render), it may take approximately 60 seconds to wake from idle spin-down.
              </p>
            </div>
          </div>
        )}

        {/* Real-time Metric Overview Stat Cards */}
        <MetricsOverview
          workers={data.workers}
          keys={data.keys}
          usage={data.usage}
        />

        {/* Inference Workers Telemetry Table Section */}
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-slate-900 tracking-tight">GPU Inference Workers</h2>
                <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                  {data.workers.length} active
                </span>
              </div>
              <p className="text-xs text-slate-500">
                GPU nodes register outbound over WebSockets (`/workers/connect`). Telemetry feeds load-aware endpoint selection.
              </p>
            </div>
            <div className="lg:hidden">
              <AutoRefresh seconds={5} />
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="bg-slate-50/75 border-b border-slate-200 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    <th className="py-3 px-4">Node / Worker ID</th>
                    <th className="py-3 px-4">Served Models</th>
                    <th className="py-3 px-4 text-right">In-Flight / Max</th>
                    <th className="py-3 px-4 text-right">Running</th>
                    <th className="py-3 px-4 text-right">Queue Waiting</th>
                    <th className="py-3 px-4 text-left">KV Cache Usage</th>
                    <th className="py-3 px-4 text-right">Connected</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.workers.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-10 px-4 text-center">
                        <div className="max-w-md mx-auto space-y-3">
                          <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-500">
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-slate-800">No GPU Workers Currently Connected</p>
                            <p className="text-xs text-slate-500 mt-1">
                              Connect your local or cloud GPU instance by launching the reverse-connect worker agent daemon:
                            </p>
                          </div>
                          <div className="bg-slate-900 text-slate-200 rounded-lg p-3 text-left font-mono text-xs overflow-x-auto shadow-inner">
                            <code>GATEWAY_URL=&quot;ws://localhost:8080/workers/connect&quot; WORKER_TOKEN=&quot;...&quot; python worker-agent/agent.py</code>
                          </div>
                          <p className="text-[11px] text-slate-400">
                            The agent initiates outbound WebSockets. No port-forwarding or public IP required on the GPU host.
                          </p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    data.workers.map((worker) => {
                      const kvPct = percent(worker.kv_cache_usage);
                      const isHighLoad = kvPct >= 85 || worker.waiting > 0;
                      return (
                        <tr key={worker.id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                              <div>
                                <div className="font-medium text-slate-900">{worker.name}</div>
                                <div className="text-[11px] font-mono text-slate-400">id: {worker.id}</div>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex flex-wrap gap-1">
                              {worker.models.length > 0 ? (
                                worker.models.map((m) => (
                                  <span
                                    key={m}
                                    className="font-mono text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200"
                                  >
                                    {m}
                                  </span>
                                ))
                              ) : (
                                <span className="text-xs text-slate-400 italic">No advertised models</span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right font-mono font-medium text-slate-900">
                            {worker.inflight}{" "}
                            <span className="text-slate-400 font-normal">/ {worker.max_concurrency}</span>
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-slate-700">
                            {worker.running}
                          </td>
                          <td className="py-3 px-4 text-right font-mono">
                            {worker.waiting > 0 ? (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">
                                {worker.waiting} queued
                              </span>
                            ) : (
                              <span className="text-slate-400">0</span>
                            )}
                          </td>
                          <td className="py-3 px-4 min-w-[140px]">
                            <div className="space-y-1">
                              <div className="flex justify-between text-xs">
                                <span className={`font-mono font-medium ${isHighLoad ? "text-amber-700" : "text-slate-700"}`}>
                                  {kvPct}%
                                </span>
                              </div>
                              <div className="w-full h-1.5 rounded-full bg-slate-100 overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all duration-500 ${
                                    kvPct >= 90
                                      ? "bg-rose-500"
                                      : kvPct >= 70
                                      ? "bg-amber-500"
                                      : "bg-emerald-500"
                                  }`}
                                  style={{ width: `${Math.min(100, Math.max(0, kvPct))}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right text-xs text-slate-500 font-mono">
                            {formatTime(worker.connected_at)}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* API Key Management Section */}
        <KeyManager keys={keyRows} />
      </main>

      {/* Subtle Enterprise Footer */}
      <footer className="mt-auto border-t border-slate-200 bg-white py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-700">CloudScale AI</span>
            <span>·</span>
            <span>Load-Aware Hybrid-Cloud LLM Inference Platform</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="font-mono">OpenAI-Compatible API: /v1/chat/completions</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
