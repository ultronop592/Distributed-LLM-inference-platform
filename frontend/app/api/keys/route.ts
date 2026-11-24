import { NextResponse } from "next/server";

import { gateway } from "@/lib/gateway";
import { isAuthenticated } from "@/lib/session";

function unauthorized() {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
}

function unreachable() {
    return NextResponse.json({ error: "Gateway unreachable" }, { status: 502 });
}

export async function POST(request: Request) {
    if (!(await isAuthenticated())) {
        return unauthorized();
    }
    const body = await request.json().catch(() => null);
    const name = typeof body?.name === "string" ? body.name.trim() : "";
    if (!name || name.length > 64) {
        return NextResponse.json({ error: "Name must be 1 to 64 characters" }, { status: 400 });
    }
    try {
        const response = await gateway("/api/keys", {
            method: "POST",
            body: JSON.stringify({ name }),
        });
        const data = await response.json().catch(() => ({}));
        return NextResponse.json(data, { status: response.status });
    } catch {
        return unreachable();
    }
}

export async function DELETE(request: Request) {
    if (!(await isAuthenticated())) {
        return unauthorized();
    }
    const id = Number(new URL(request.url).searchParams.get("id"));
    if (!Number.isInteger(id) || id <= 0) {
        return NextResponse.json({ error: "Invalid key id" }, { status: 400 });
    }
    try {
        const response = await gateway(`/api/keys/${id}`, { method: "DELETE" });
        const data = await response.json().catch(() => ({}));
        return NextResponse.json(data, { status: response.status });
    } catch {
        return unreachable();
    }
}