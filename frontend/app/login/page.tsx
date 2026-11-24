"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

export default function LoginPage() {
    const router = useRouter();
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    async function submit(event: FormEvent) {
        event.preventDefault();
        setBusy(true);
        setError(null);
        const response = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password }),
        });
        setBusy(false);
        if (!response.ok) {
            setError("Invalid password");
            return;
        }
        router.push("/");
        router.refresh();
    }

    return (
        <main className="mx-auto flex min-h-screen max-w-sm items-center p-6">
            <form onSubmit={submit} className="w-full space-y-4">
                <h1 className="text-2xl font-semibold">CloudScale AI</h1>
                <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Dashboard password"
                    autoFocus
                    className="w-full rounded border border-neutral-400 bg-transparent px-3 py-2"
                />
                {error && <p className="text-sm text-red-500">{error}</p>}
                <button
                    type="submit"
                    disabled={busy || password.length === 0}
                    className="w-full rounded bg-neutral-900 px-3 py-2 text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
                >
                    {busy ? "Signing in" : "Sign in"}
                </button>
            </form>
        </main>
    );
}