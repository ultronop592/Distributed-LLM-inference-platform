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

export default function KeyManager({ keys }: { keys: KeyRow[] }) {
    const router = useRouter();
    const [name, setName] = useState("");
    const [createdKey, setCreatedKey] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    async function createKey(event: FormEvent) {
        event.preventDefault();
        setBusy(true);
        setError(null);
        setCreatedKey(null);
        const response = await fetch("/api/keys", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
        });
        const data = await response.json().catch(() => ({}));
        setBusy(false);
        if (!response.ok) {
            setError(messageFrom(data, "Could not create key"));
            return;
        }
        setCreatedKey(data.key);
        setName("");
        router.refresh();
    }

    async function revoke(id: number) {
        if (!confirm("Revoke this key? Clients using it will stop working.")) {
            return;
        }
        setError(null);
        const response = await fetch(`/api/keys?id=${id}`, { method: "DELETE" });
        if (!response.ok) {
            setError("Could not revoke key");
        }
        router.refresh();
    }

    return (
        <section className="space-y-4">
            <h2 className="text-lg font-semibold">API keys</h2>

            <form onSubmit={createKey} className="flex gap-2">
                <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Key name"
                    maxLength={64}
                    className="flex-1 rounded border border-neutral-400 bg-transparent px-3 py-2"
                />
                <button
                    type="submit"
                    disabled={busy || name.trim().length === 0}
                    className="rounded bg-neutral-900 px-4 py-2 text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
                >
                    Create key
                </button>
            </form>

            {error && <p className="text-sm text-red-500">{error}</p>}

            {createdKey && (
                <div className="space-y-2 rounded border border-amber-500 p-3">
                    <p className="text-sm">Copy this key now. It is shown only once.</p>
                    <div className="flex gap-2">
                        <code className="flex-1 break-all rounded bg-neutral-200 px-2 py-1 text-sm dark:bg-neutral-800">
                            {createdKey}
                        </code>
                        <button
                            onClick={() => navigator.clipboard.writeText(createdKey)}
                            className="rounded border border-neutral-400 px-3 py-1 text-sm"
                        >
                            Copy
                        </button>
                        <button
                            onClick={() => setCreatedKey(null)}
                            className="rounded border border-neutral-400 px-3 py-1 text-sm"
                        >
                            Hide
                        </button>
                    </div>
                </div>
            )}

            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                    <thead>
                        <tr className="border-b border-neutral-400">
                            <th className="py-2 pr-4">Name</th>
                            <th className="pr-4">Prefix</th>
                            <th className="pr-4">Created (UTC)</th>
                            <th className="pr-4 text-right">Requests</th>
                            <th className="pr-4 text-right">Prompt tokens</th>
                            <th className="pr-4 text-right">Completion tokens</th>
                            <th />
                        </tr>
                    </thead>
                    <tbody>
                        {keys.length === 0 && (
                            <tr>
                                <td colSpan={7} className="py-3 text-neutral-500">
                                    No keys yet
                                </td>
                            </tr>
                        )}
                        {keys.map((key) => (
                            <tr key={key.id} className="border-b border-neutral-300 dark:border-neutral-700">
                                <td className="py-2 pr-4">{key.name}</td>
                                <td className="pr-4 font-mono">{key.prefix}</td>
                                <td className="pr-4">{key.created}</td>
                                <td className="pr-4 text-right">{key.requests}</td>
                                <td className="pr-4 text-right">{key.promptTokens}</td>
                                <td className="pr-4 text-right">{key.completionTokens}</td>
                                <td className="text-right">
                                    {key.revoked ? (
                                        <span className="text-neutral-500">revoked</span>
                                    ) : (
                                        <button onClick={() => revoke(key.id)} className="text-red-500">
                                            Revoke
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}