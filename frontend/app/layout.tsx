import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CloudScale AI — Distributed LLM Serving Gateway",
  description: "Load-aware inference gateway, reverse-connected GPU workers, and multi-tenant telemetry console.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full bg-slate-50 text-slate-900 antialiased">
      <body className="min-h-full flex flex-col font-sans">
        {children}
      </body>
    </html>
  );
}
