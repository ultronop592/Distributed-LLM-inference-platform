"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

export type KeyRow = {
  id: number;
  name: string;
  prefix: string;
  created: string;
  revoked: boolean;
  requests: number;
  promptTokens: number;
  completionTokens: number;
};

function messageFrom(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "error" in data) {
    const error = (data as { error: unknown }).error;
    if (typeof error === "string") {
      return error;
    }
    if (error && typeof error === "object" && "message" in error) {
      return String((error as { message: unknown }).message);
    }
  }
  return fallback;
}

function formatNumber(num: number): string {
  return new Intl.NumberFormat("en-US").format(num);
}

export default function KeyManager({ keys }: { keys: KeyRow[] }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedCurl, setCopiedCurl] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revokingId, setRevokingId] = useState<number | null>(null);

  async function createKey(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    setCreatedKey(null);
    setCopiedKey(false);

    try {
      const response = await fetch("/api/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      const data = await response.json().catch(() => ({}));
      setBusy(false);
      if (!response.ok) {
        setError(messageFrom(data, "Failed to create API key"));
        return;
      }
      setCreatedKey(data.key);
      setName("");
      router.refresh();
    } catch {
      setBusy(false);
      setError("Network error: Could not reach gateway API");
    }
  }

  async function revoke(id: number, keyName: string) {
    if (!confirm(`Are you sure you want to revoke key "${keyName}"? All client requests using this key will be rejected immediately.`)) {
      return;
    }
    setError(null);
    setRevokingId(id);
    try {
      const response = await fetch(`/api/keys?id=${id}`, { method: "DELETE" });
      setRevokingId(null);
      if (!response.ok) {
        setError("Failed to revoke key on gateway");
      }
      router.refresh();
    } catch {
      setRevokingId(null);
      setError("Network error while attempting revocation");
    }
  }

  function handleCopyKey() {
    if (!createdKey) return;
    navigator.clipboard.writeText(createdKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  }

  const sampleKey = createdKey || (keys.find((k) => !k.revoked)?.prefix ? `${keys.find((k) => !k.revoked)?.prefix}...` : "csk_your_key_here");
  const curlExample = `curl http://localhost:8080/v1/chat/completions \\
  -H "Authorization: Bearer ${sampleKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"model": "Qwen/Qwen2.5-0.5B-Instruct", "messages": [{"role": "user", "content": "Hello!"}], "stream": true}'`;

  function handleCopyCurl() {
    navigator.clipboard.writeText(curlExample);
    setCopiedCurl(true);
    setTimeout(() => setCopiedCurl(false), 2000);
  }

  return (
    <section className="space-y-6">
      {/* Header & Create Form */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 tracking-tight">API Key Management</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Generate SHA-256 hashed bearer tokens for authorized OpenAI-compatible client completions.
            </p>
          </div>
        </div>

        <form onSubmit={createKey} className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Key label, e.g. web-app-prod, evaluation-suite"
              maxLength={64}
              disabled={busy}
              className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-500 transition-all shadow-sm"
            />
          </div>

          <button
            type="submit"
            disabled={busy || name.trim().length === 0}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-900/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer shrink-0"
          >
            {busy ? (
              <>
                <svg className="w-4 h-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Generating...</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
                <span>Create Secret Key</span>
              </>
            )}
          </button>
        </form>

        {error && (
          <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800 flex items-center gap-2">
            <svg className="w-4 h-4 text-rose-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {/* Secret Key Modal/Alert Banner */}
        {createdKey && (
          <div className="rounded-xl border border-amber-300 bg-amber-50/70 p-5 shadow-sm space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2 text-amber-900 font-semibold text-sm">
                <svg className="w-5 h-5 text-amber-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>Save Your Secret API Key</span>
              </div>
              <button
                onClick={() => setCreatedKey(null)}
                className="text-amber-700 hover:text-amber-900 p-1 rounded hover:bg-amber-100 transition-colors cursor-pointer"
                title="Dismiss key view"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <p className="text-xs text-amber-800">
              Please copy and store this API key now. For your security, this key is hashed with SHA-256 and will never be shown again.
            </p>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 bg-slate-900 rounded-lg p-3 shadow-inner">
              <code className="flex-1 font-mono text-xs text-emerald-400 break-all select-all">
                {createdKey}
              </code>
              <button
                onClick={handleCopyKey}
                className="inline-flex items-center justify-center gap-1.5 rounded-md bg-white/10 hover:bg-white/20 text-white text-xs font-medium px-3 py-1.5 transition-colors cursor-pointer shrink-0"
              >
                {copiedKey ? (
                  <>
                    <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-emerald-400 font-semibold">Copied!</span>
                  </>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    <span>Copy Key</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* API Keys Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden space-y-0">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Provisioned Keys</h3>
          <span className="text-xs text-slate-500 font-mono">
            {keys.filter((k) => !k.revoked).length} active keys
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-slate-50/75 border-b border-slate-200 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <th className="py-3 px-4">Label</th>
                <th className="py-3 px-4">Key Prefix</th>
                <th className="py-3 px-4">Created Date</th>
                <th className="py-3 px-4 text-right">Requests</th>
                <th className="py-3 px-4 text-right">Prompt Tokens</th>
                <th className="py-3 px-4 text-right">Completion Tokens</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {keys.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 px-4 text-center text-slate-500 text-xs">
                    No API keys created yet. Generate your first key using the form above.
                  </td>
                </tr>
              ) : (
                keys.map((key) => (
                  <tr key={key.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3 px-4 font-medium text-slate-900">
                      {key.name}
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                        {key.prefix}•••
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500 font-mono">
                      {key.created}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-slate-700">
                      {formatNumber(key.requests)}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-slate-700">
                      {formatNumber(key.promptTokens)}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-slate-700">
                      {formatNumber(key.completionTokens)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {key.revoked ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                          Revoked
                        </span>
                      ) : (
                        <button
                          onClick={() => revoke(key.id, key.name)}
                          disabled={revokingId === key.id}
                          className="inline-flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 border border-rose-200/80 transition-colors disabled:opacity-50 cursor-pointer"
                        >
                          {revokingId === key.id ? "Revoking..." : "Revoke"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Developer Testing Helper Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-slate-900 font-semibold text-sm">cURL Quick Test</span>
            <span className="text-[11px] bg-slate-100 text-slate-600 border border-slate-200 px-2 py-0.5 rounded font-mono">
              /v1/chat/completions
            </span>
          </div>
          <button
            onClick={handleCopyCurl}
            className="inline-flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 font-medium px-2.5 py-1 rounded border border-slate-200 hover:bg-slate-50 transition-colors cursor-pointer"
          >
            {copiedCurl ? (
              <>
                <svg className="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
                </svg>
                <span className="text-emerald-600 font-semibold">Copied command!</span>
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                <span>Copy cURL</span>
              </>
            )}
          </button>
        </div>
        <div className="bg-slate-900 rounded-lg p-3 overflow-x-auto text-slate-200 font-mono text-xs shadow-inner">
          <pre>{curlExample}</pre>
        </div>
      </div>
    </section>
  );
}
