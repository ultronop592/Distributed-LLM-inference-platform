import { redirect } from "next/navigation";

import AutoRefresh from "@/components/auto-refresh";
import KeyManager, { type KeyRow } from "@/components/key-manager";
import SignOut from "@/components/sign-out";
import { loadDashboard } from "@/lib/gateway";
import { isAuthenticated } from "@/lib/session";

export const dynamic = "force-dynamic";

function formatTime(seconds: number): string {
  return new Date(seconds * 1000).toISOString().replace("T", " ").slice(0, 16);
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
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

  const inferenceLabel =
    data.inference === "ok" ? "GPU worker online" : "No GPU worker online";

  return (
    <main className="mx-auto max-w-5xl space-y-8 p-6">
      <AutoRefresh seconds={5} />

      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">CloudScale AI</h1>
          <p className="text-sm text-neutral-500">
            Gateway {data.gatewayOnline ? "online" : "unreachable"} · {inferenceLabel}
          </p>
        </div>
        <SignOut />
      </header>

      {data.error && (
        <p className="rounded border border-red-500 p-3 text-sm text-red-500">
          {data.error}. If the gateway is on a free tier, it may be waking up and can take about a
          minute.
        </p>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Workers</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-neutral-400">
                <th className="py-2 pr-4">Name</th>
                <th className="pr-4">Models</th>
                <th className="pr-4 text-right">In flight</th>
                <th className="pr-4 text-right">Running</th>
                <th className="pr-4 text-right">Waiting</th>
                <th className="pr-4 text-right">KV cache</th>
                <th className="text-right">Connected (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {data.workers.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-3 text-neutral-500">
                    No workers connected
                  </td>
                </tr>
              )}
              {data.workers.map((worker) => (
                <tr key={worker.id} className="border-b border-neutral-300 dark:border-neutral-700">
                  <td className="py-2 pr-4">{worker.name}</td>
                  <td className="pr-4">{worker.models.join(", ")}</td>
                  <td className="pr-4 text-right">
                    {worker.inflight} / {worker.max_concurrency}
                  </td>
                  <td className="pr-4 text-right">{worker.running}</td>
                  <td className="pr-4 text-right">{worker.waiting}</td>
                  <td className="pr-4 text-right">{percent(worker.kv_cache_usage)}</td>
                  <td className="text-right">{formatTime(worker.connected_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <KeyManager keys={keyRows} />
    </main>
  );
}