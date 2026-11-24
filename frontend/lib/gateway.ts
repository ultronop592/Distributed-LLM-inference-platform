export type Worker = {
    id: string;
    name: string;
    models: string[];
    max_concurrency: number;
    inflight: number;
    running: number;
    waiting: number;
    kv_cache_usage: number;
    connected_at: number;
};

export type ApiKey = {
    id: number;
    name: string;
    prefix: string;
    created_at: number;
    revoked_at: number | null;
};

export type UsageRow = {
    id: number;
    name: string;
    prefix: string;
    requests: number;
    prompt_tokens: number;
    completion_tokens: number;
};

export type DashboardData = {
    gatewayOnline: boolean;
    inference: string;
    workers: Worker[];
    keys: ApiKey[];
    usage: UsageRow[];
    error?: string;
};

function baseUrl(): string {
    return process.env.GATEWAY_URL ?? "http://localhost:8080";
}

export async function gateway(path: string, init: RequestInit = {}): Promise<Response> {
    const token = process.env.ADMIN_TOKEN;
    if (!token) {
        throw new Error("ADMIN_TOKEN is not set");
    }
    return fetch(`${baseUrl()}${path}`, {
        ...init,
        cache: "no-store",
        signal: AbortSignal.timeout(20000),
        headers: {
            ...(init.headers ?? {}),
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
        },
    });
}

async function getJson<T>(path: string): Promise<T> {
    const response = await gateway(path);
    if (!response.ok) {
        throw new Error(`${path} returned ${response.status}`);
    }
    return (await response.json()) as T;
}

export async function loadDashboard(): Promise<DashboardData> {
    try {
        const [workers, keys, usage, health] = await Promise.all([
            getJson<{ workers: Worker[] }>("/api/workers"),
            getJson<{ keys: ApiKey[] }>("/api/keys"),
            getJson<{ usage: UsageRow[] }>("/api/usage"),
            fetch(`${baseUrl()}/healthz`, { cache: "no-store", signal: AbortSignal.timeout(20000) }),
        ]);
        const healthBody = (await health.json().catch(() => ({}))) as { status?: string };
        return {
            gatewayOnline: true,
            inference: healthBody.status ?? "unknown",
            workers: workers.workers,
            keys: keys.keys,
            usage: usage.usage,
        };
    } catch (error) {
        return {
            gatewayOnline: false,
            inference: "unknown",
            workers: [],
            keys: [],
            usage: [],
            error: error instanceof Error ? error.message : "Gateway unreachable",
        };
    }
}