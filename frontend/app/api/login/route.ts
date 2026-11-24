import { NextResponse } from "next/server";

import { passwordMatches, setSession } from "@/lib/session";

export async function POST(request: Request) {
    const body = await request.json().catch(() => null);
    const password = typeof body?.password === "string" ? body.password : "";
    if (!password || !passwordMatches(password)) {
        return NextResponse.json({ error: "Invalid password" }, { status: 401 });
    }
    await setSession();
    return NextResponse.json({ ok: true });
}
