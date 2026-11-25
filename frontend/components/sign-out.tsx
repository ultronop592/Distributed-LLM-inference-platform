"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function SignOut() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    try {
      setBusy(true);
      await fetch("/api/logout", { method: "POST" });
      router.push("/login");
      router.refresh();
    } catch {
      setBusy(false);
    }
  }

  return (
    <button
      onClick={signOut}
      disabled={busy}
      title="Sign out of administrative session"
      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition-all hover:bg-slate-50 hover:border-slate-300 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10 disabled:opacity-60 cursor-pointer"
    >
      <svg
        className={`w-3.5 h-3.5 text-slate-500 ${busy ? "animate-spin" : ""}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth="2"
      >
        {busy ? (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M4 12a8 8 0 018-8v8H4z"
          />
        ) : (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75"
          />
        )}
      </svg>
      {busy ? "Signing out..." : "Sign out"}
    </button>
  );
}
