"use client";

import { useRouter } from "next/navigation";

export default function SignOut() {
    const router = useRouter();

    async function signOut() {
        await fetch("/api/logout", { method: "POST" });
        router.push("/login");
        router.refresh();
    }

    return (
        <button onClick={signOut} className="rounded border border-neutral-400 px-3 py-1 text-sm">
            Sign out
        </button>
    );
}