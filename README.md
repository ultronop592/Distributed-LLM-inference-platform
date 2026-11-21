# CloudScale AI

**A hybrid-cloud LLM serving platform with a load-aware inference gateway, Kubernetes-native GPU workers, and llm-d routing, built and measured on constrained hardware.**

The control plane, gateway and dashboard run in the cloud. GPU workers run vLLM on Kubernetes (k3s) on a machine you own and connect outbound to the cloud gateway. No inbound ports are opened on the GPU machine.

> **Status:** in active development. Everything under "Planned" is a target, not a claim. See [Validation Status](#validation-status) for what has actually been tested.

---

## Table of Contents

1. [Why this project](#why-this-project)
2. [Key features](#key-features)
3. [Architecture](#architecture)
4. [Tech stack](#tech-stack)
5. [Hardware and honest limits](#hardware-and-honest-limits)
6. [Repository structure](#repository-structure)
7. [Getting started](#getting-started)
8. [API](#api)
9. [Observability and benchmarks](#observability-and-benchmarks)
10. [Deployment](#deployment)
11. [Security](#security)
12. [Validation status](#validation-status)
13. [Roadmap](#roadmap)
14. [Documentation](#documentation)
15. [License](#license)

---

## Why this project

Running a model with vLLM is easy. Operating inference as a service is harder: authenticating callers, enforcing quotas, routing around unhealthy or saturated workers, shedding load cleanly, scaling replicas, and proving performance with reproducible numbers.

CloudScale AI focuses on that operational layer. It uses real vLLM inference (no mocked responses) and treats a small GPU as a constraint to engineer around.

## Key features

- **OpenAI-compatible API** with Server-Sent Events streaming (`/v1/chat/completions`).
- **Smart gateway**
  - API keys, hashed at rest, with per-key rate limits and token budgets
  - Load-aware endpoint picker that scores workers using vLLM metrics (queue depth, KV-cache usage)
  - Backpressure and load shedding with clear `429` / `503` responses
  - Priority handling for different key tiers
- **Multi-model routing:** short or simple prompts go to a small model, harder ones to a larger quantized model.
- **Reverse-connect worker agent:** GPU nodes register with the cloud control plane over an outbound WebSocket and stream tokens back through it.
- **Kubernetes operations:** pinned images, GPU scheduling, probes, model cache volume, Helm chart, queue-depth autoscaling.
- **llm-d integration:** Gateway API Inference Extension, `InferencePool` and the llm-d Endpoint Picker, compared against the custom picker and round-robin.
- **Observability:** Prometheus and Grafana dashboards for TTFT, TPOT, ITL, throughput, queue time, error rate and GPU metrics.
- **Chaos and load testing:** Locust benchmarks and worker-kill recovery tests with full reproducibility metadata.

## Architecture

```
                 Client / SDK / Dashboard
                          |
                          v
        +-----------------------------------+
        |  Render (free tier)               |
        |  FastAPI control plane + gateway  |
        |  - auth, RBAC, API keys, quotas   |
        |  - model registry, deployments    |
        |  - endpoint picker, streaming     |
        +-----------------------------------+
              |                        ^
              v                        | outbound WebSocket
        PostgreSQL (external)          | (opened by the worker)
                                       |
        +-----------------------------------+
        |  GPU machine (your hardware)      |
        |  worker agent                     |
        |        |                          |
        |        v                          |
        |  k3s + NVIDIA device plugin       |
        |  llm-d Router (EPP) + InferencePool
        |     |         |                   |
        |   vLLM       vLLM    (replicas)   |
        |        |                          |
        |  Prometheus + Grafana             |
        +-----------------------------------+
```

**Control plane vs data plane:** management operations (users, models, deployments, keys) are kept separate from latency-sensitive inference traffic.

**Request flow:**
1. A client sends a chat completion request with an API key to the gateway.
2. The gateway authenticates, checks the rate limit and token budget, and selects a healthy worker.
3. The request goes to the worker agent over its outbound WebSocket.
4. The agent forwards it to the cluster, where the llm-d Router picks a vLLM pod.
5. Tokens stream back along the same path to the client.

## Tech stack

| Area | Technology |
|---|---|
| Frontend | Next.js + TypeScript + Tailwind CSS |
| Control plane and gateway | Python, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL |
| Inference engine | vLLM |
| Models | Hugging Face Hub (Qwen2.5-0.5B-Instruct, Qwen2.5-1.5B-Instruct-AWQ) |
| Containers and orchestration | Docker, k3s, Helm |
| Distributed inference | llm-d, Gateway API Inference Extension |
| Observability | Prometheus, Grafana |
| Load testing | Locust |
| CI/CD | GitHub Actions, GHCR |
| Cloud hosting | Render (free tier) for control plane and gateway |

Exact versions are recorded in [`docs/versions.md`](docs/versions.md) and pinned in lockfiles, Dockerfiles and Helm values.

## Hardware and honest limits

Development target:

| Item | Value |
|---|---|
| OS | Windows with WSL2 |
| GPU | NVIDIA RTX 2050, 4 GB VRAM |

What this means:

- Models are limited to small or quantized ones (0.5B fp16, 1.5B AWQ int4).
- Multiple replicas share one GPU, so replica tests validate **routing and failover**, not real horizontal throughput scaling.
- Prefill/decode disaggregation, NIXL and large-scale cache-aware routing gains need multi-GPU or multi-node hardware and are **out of scope** for validation here.
- Inference is only available while the GPU machine is online. When it is offline, the API stays up and returns a clear "no GPU worker online" error.
- The Render free tier spins down after 15 minutes of inactivity and takes about a minute to wake. Free Postgres on Render expires, so the database is hosted externally. Check each provider's current limits.

## Repository structure

```
cloudscale-ai/
├── frontend/                 # Next.js dashboard
├── control-plane/            # FastAPI control plane and gateway
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── auth/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── migrations/
│   └── tests/
├── worker-agent/             # Outbound-connecting GPU worker agent
├── inference/
│   ├── vllm/
│   ├── llm-d/
│   └── gateway/
├── infrastructure/
│   ├── docker/
│   ├── kubernetes/
│   └── helm/
├── observability/
│   ├── prometheus/
│   ├── grafana/
│   └── alerts/
├── load-testing/
│   ├── locust/
│   └── benchmarks/
├── docs/
│   ├── architecture.md
│   ├── decisions/            # architecture decision records
│   ├── versions.md
│   ├── benchmarks.md
│   └── security.md
├── render.yaml
├── PLAN.md
└── README.md
```

## Getting started

### Prerequisites

- Windows with WSL2 (Ubuntu) and a current NVIDIA driver on the Windows side
- Docker
- Python and Node.js (see `docs/versions.md`)
- A Hugging Face account for model downloads

### 1. Verify the GPU in WSL2

```bash
nvidia-smi
```

### 2. Run vLLM directly

```bash
pip install vllm==<PINNED_VERSION>
vllm serve Qwen/Qwen2.5-0.5B-Instruct --revision <PINNED_REVISION> --max-model-len 2048 --gpu-memory-utilization 0.85 --port 8000
```

Test it:

```bash
curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"Qwen/Qwen2.5-0.5B-Instruct","messages":[{"role":"user","content":"Hello"}],"stream":true}'
```

### 3. Run the control plane locally

```bash
cd control-plane
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8080
```

### 4. Run the dashboard

```bash
cd frontend
npm ci
npm run dev
```

### 5. Start the worker agent

```bash
cd worker-agent
pip install -r requirements.txt
python -m agent --gateway-url <GATEWAY_URL> --token <WORKER_TOKEN> --vllm-url http://localhost:8000
```

### 6. Kubernetes (k3s) deployment

```bash
helm install cloudscale infrastructure/helm/cloudscale -f infrastructure/helm/cloudscale/values.local.yaml
```

Detailed steps for GPU scheduling, the model cache volume and llm-d are in [`docs/architecture.md`](docs/architecture.md).

### Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Signing key for tokens |
| `WORKER_REGISTRATION_TOKEN` | Shared secret for worker registration |
| `VLLM_BASE_URL` | vLLM endpoint used by the worker agent |
| `ALLOWED_ORIGINS` | CORS origins for the dashboard |

Never commit secrets. Use `.env` locally and Render environment variables in the cloud.

## API

### Chat completions

```
POST /v1/chat/completions
Authorization: Bearer <API_KEY>
```

```json
{
  "model": "Qwen/Qwen2.5-0.5B-Instruct",
  "messages": [{"role": "user", "content": "Explain KV cache in one sentence."}],
  "stream": true,
  "max_tokens": 128
}
```

### Other endpoints (planned)

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Gateway health |
| `GET` | `/v1/models` | Registered and available models |
| `POST` | `/api/auth/login` | Dashboard sign-in |
| `POST` | `/api/keys` | Create an API key (shown once) |
| `DELETE` | `/api/keys/{id}` | Revoke an API key |
| `GET` | `/api/workers` | Registered workers and their status |
| `GET` | `/api/deployments` | Deployment status and events |

### Error behavior

| Status | Meaning |
|---|---|
| `401` | Missing or invalid API key |
| `429` | Rate limit or token budget exceeded |
| `503` | No healthy worker online, or load shed |
| `504` | Worker timed out |

## Observability and benchmarks

Metrics tracked:

| Metric | Meaning |
|---|---|
| TTFT | Time to first token |
| TPOT | Time per output token after the first |
| ITL | Gap between generated tokens |
| Throughput | Tokens per second per worker and overall |
| Queue time | Wait before inference begins |
| Error rate | Failed requests by status and reason |
| GPU utilization and memory | From the GPU exporter |

### Benchmark methodology

Every published result must include: GPU model and VRAM, OS and driver, vLLM version, model and revision, quantization, prompt length, output length, concurrency, warm-up duration, test duration and all relevant vLLM flags.

Planned comparisons, each run with Locust at 1, 5, 10 and 25 clients where the hardware allows:

1. Qwen2.5-0.5B fp16 vs Qwen2.5-1.5B AWQ
2. Single worker vs two replicas sharing the GPU
3. Round-robin vs custom load-aware picker vs llm-d Endpoint Picker
4. Multi-model routing vs single-model baseline

Results will be added to [`docs/benchmarks.md`](docs/benchmarks.md) once measured. No numbers are published without their conditions.

## Deployment

| Component | Location |
|---|---|
| Dashboard | Vercel or Render static site |
| Control plane and gateway | Render free web service (single service, separate modules) |
| Database | External managed PostgreSQL free tier |
| Worker agent, k3s, vLLM, llm-d, Prometheus, Grafana | Your own GPU machine |
| Model weights | Hugging Face Hub |

The Render service is described in `render.yaml`. CI builds, tests and scans images with GitHub Actions and deploys on merge to `main`.

**Cold starts:** the gateway may take about a minute to wake after idle. The agent reconnects with exponential backoff, and the dashboard shows a "waking up" state.

## Security

- API keys hashed at rest, shown once, revocable and rotatable
- Role-based access control for administrative actions
- TLS on public endpoints
- Per-key rate limits, request size limits and timeouts
- Secrets in environment variables or Kubernetes Secrets, never in source control
- Worker registration authenticated by token, outbound connections only
- Prompt and completion content not logged by default
- Pinned dependencies and container images, with dependency and image scanning in CI

See [`docs/security.md`](docs/security.md) for details.

## Validation status

This table is updated only when something has been run and verified.

| Capability | Status |
|---|---|
| Control plane (auth, API keys, registry) | Not started |
| vLLM serving on RTX 2050 | Not started |
| Streaming through gateway | Not started |
| Worker agent over WebSocket | Not started |
| k3s with GPU scheduling | Not started |
| Prometheus and Grafana | Not started |
| Load-aware picker | Not started |
| llm-d routing (simulator) | Not started |
| llm-d routing (real vLLM) | Not started |
| Autoscaling and chaos tests | Not started |
| Render deployment | Not started |

## Roadmap

See [`PLAN.md`](PLAN.md) for the full week-by-week plan.

- [ ] Phase 1: vLLM serving and repo setup
- [ ] Phase 2: Gateway and control plane
- [ ] Phase 3: Worker agent and registration
- [ ] Phase 4: Containers and k3s
- [ ] Phase 5: Observability and load-aware routing
- [ ] Phase 6: llm-d integration
- [ ] Phase 7: Autoscaling and chaos tests
- [ ] Phase 8: Cloud deployment, benchmarks and documentation

**Out of scope for now:** multi-GPU scaling, prefill/decode disaggregation, NIXL, Terraform, Argo CD, OpenTelemetry tracing.

## Documentation

- [`PLAN.md`](PLAN.md): implementation plan
- [`docs/architecture.md`](docs/architecture.md): architecture details
- [`docs/decisions/`](docs/decisions): architecture decision records
- [`docs/benchmarks.md`](docs/benchmarks.md): benchmark results and methodology
- [`docs/security.md`](docs/security.md): security notes
- [`docs/versions.md`](docs/versions.md): pinned versions

References: [vLLM](https://docs.vllm.ai/), [llm-d](https://llm-d.ai/), [Kubernetes](https://kubernetes.io/docs/), [Prometheus](https://prometheus.io/docs/), [Grafana](https://grafana.com/docs/)

## Author

Srajal Tiwari

## License

To be decided (MIT recommended).