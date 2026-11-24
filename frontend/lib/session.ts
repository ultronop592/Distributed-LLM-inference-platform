import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

const COOKIE_NAME = "cs_session";
const MAX_AGE_SECONDS = 8 * 60 * 60;

function secret(): string {
    const value = process.env.SESSION_SECRET;
    if (!value || value.length < 32) {
        throw new Error("SESSION_SECRET must be set to at least 32 characters");
    }
    return value;
}

function sign(payload: string): string {
    return createHmac("sha256", secret()).update(payload).digest("hex");
}

export function passwordMatches(candidate: string): boolean {
    const expected = process.env.DASHBOARD_PASSWORD;
    if (!expected) {
        return false;
    }
    const left = createHmac("sha256", secret()).update(candidate).digest();
    const right = createHmac("sha256", secret()).update(expected).digest();
    return timingSafeEqual(left, right);
}

function createSessionValue(): string {
    const payload = String(Math.floor(Date.now() / 1000) + MAX_AGE_SECONDS);
    return `${payload}.${sign(payload)}`;
}

function isValid(value: string | undefined): boolean {
    if (!value) {
        return false;
    }
    const [payload, signature] = value.split(".");
    if (!payload || !signature) {
        return false;
    }
    const given = Buffer.from(signature);
    const expected = Buffer.from(sign(payload));
    if (given.length !== expected.length || !timingSafeEqual(given, expected)) {
        return false;
    }
    return Number(payload) > Math.floor(Date.now() / 1000);
}

export async function isAuthenticated(): Promise<boolean> {
    const store = await cookies();
    return isValid(store.get(COOKIE_NAME)?.value);
}

export async function setSession(): Promise<void> {
    const store = await cookies();
    store.set(COOKIE_NAME, createSessionValue(), {
        httpOnly: true,
        sameSite: "strict",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge: MAX_AGE_SECONDS,
    });
}

export async function clearSession(): Promise<void> {
    const store = await cookies();
    store.delete(COOKIE_NAME);
}