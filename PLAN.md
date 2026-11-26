# CloudScale AI: Project Plan

Working plan for building CloudScale AI in 8 weeks, part-time. Update the checkboxes and the decision log as you go.

## 1. Goal

Build a hybrid-cloud LLM inference platform with real vLLM serving, a load-aware gateway, Kubernetes GPU workers, llm-d routing, and reproducible benchmarks, on a single 4 GB GPU.

**Success looks like:** a public README and live dashboard, a working OpenAI-compatible streaming API, a benchmark report with full conditions, and a short demo video showing a request, load-based scaling, and a worker kill with recovery.

## 2. Constraints and decisions

| Item | Decision |
|---|---|
| Hardware | Windows, WSL2, NVIDIA RTX 2050 4 GB |
| Models | Qwen2.5-0.5B-Instruct (fp16), Qwen2.5-1.5B-Instruct-AWQ |
| Cloud | Render free tier for control plane and gateway; external free Postgres; Vercel or Render static for dashboard |
| Kubernetes | k3s in WSL2 with NVIDIA device plugin |
| Distributed inference | llm-d Router (EPP) and InferencePool, validated first with the simulator, then with real vLLM |
| GPU to cloud link | Worker agent opens an outbound WebSocket to the gateway |
| Honest limits | One GPU shared by replicas, GPU node only online when your PC is on, Render free tier sleeps after 15 minutes |

Verify current Render, database and Hugging Face free-tier limits before relying on them, since they change.

## 3. Rules for the whole project

1. Get one thing working end to end before adding the next layer.
2. Pin every version (vLLM, CUDA-related images, Python and Node dependencies, Helm charts, model revisions). Record them in `docs/versions.md`.
3. Never claim something is validated until it has been run. Keep the README validation table honest.
4. Every benchmark result records its full conditions.
5. Write a short decision record in `docs/decisions/` for each major choice.
6. Keep prompt and completion content out of logs.
7. Commit small and often, with CI green on `main`.

## 4. Week-by-week plan

### Week 1: Foundations and real vLLM

**Goal:** vLLM serves a real model on your GPU with streaming verified.

- [ ] Create the repo with `control-plane/`, `inference/`, `docs/` and the top-level files
- [ ] Install WSL2 Ubuntu and confirm `nvidia-smi` works inside it
- [ ] Create a Python virtual environment and install a pinned vLLM version
- [ ] Serve Qwen2.5-0.5B-Instruct with `--max-model-len 2048` and `--gpu-memory-utilization 0.85`
- [ ] Verify `/v1/chat/completions` with and without streaming
- [ ] Check `/metrics` and note which vLLM metrics are exposed
- [ ] Record GPU memory use and baseline latency for a few prompts
- [ ] Write ADR-001 (gateway approach: custom FastAPI proxy) and fill `docs/versions.md`

**Done when:** a streaming curl request works and the versions are pinned.
**Risk:** WSL2 or CUDA issues. Fix the driver and WSL GPU support before anything else.

### Week 2: Gateway v1

**Goal:** an authenticated, rate-limited streaming proxy in front of vLLM.

- [ ] FastAPI app skeleton with config, logging and `/healthz`
- [ ] API key creation, hashed storage, one-time display, revoke
- [ ] Bearer authentication on `/v1/chat/completions`
- [ ] Streaming proxy that forwards SSE and handles client disconnects
- [ ] Per-key rate limit and request size limit
- [ ] Per-key token counting from vLLM usage data
- [ ] Consistent error format and status codes (401, 429, 503, 504)
- [ ] Unit and integration tests, plus a Locust smoke test

**Done when:** unauthorized requests are rejected, rate limits trigger, and streaming survives a client disconnect.

### Week 3: Control plane and worker agent

**Goal:** a worker appears in the system by connecting outbound.

- [x] PostgreSQL schema and Alembic migrations (users, keys, models, deployments, workers, usage)
- [ ] Authentication and RBAC (admin and user roles)
- [ ] Model registry endpoints (create, read, update, validate)
- [x] WebSocket registration protocol: worker token, heartbeat, status, capacity
- [x] Request and streamed-token forwarding over the WebSocket
- [ ] Agent reconnect with exponential backoff
- [x] Minimal Next.js dashboard: sign in, models, workers, API keys
- [x] Write ADR-002 (worker connection protocol)

**Done when:** killing and restarting the agent makes the worker disappear and reappear in the dashboard, and requests stream through it.

### Week 4: Containers and Kubernetes

**Goal:** vLLM runs as a GPU pod in k3s.

- [ ] Dockerfiles for control plane, gateway, agent and dashboard with pinned bases
- [ ] Install k3s in WSL2, the NVIDIA Container Toolkit and the NVIDIA device plugin
- [ ] Confirm a test pod can request `nvidia.com/gpu: 1`
- [ ] Deploy vLLM with resource limits, readiness and liveness probes, and a model cache volume
- [ ] Handle slow model load in probes (startup probe)
- [ ] Helm chart with values for local and cloud
- [ ] Secrets via Kubernetes Secrets
- [ ] Write ADR-003 (how the control plane tracks deployments)

**Done when:** `helm install` brings up a vLLM pod that passes readiness and serves requests through the agent.
**Fallback:** if GPU passthrough in k3s blocks you, keep vLLM running in Docker, deploy a mock worker on kind to validate the manifests, and label this clearly in the README.

### Week 5: Observability and load-aware picker

**Goal:** see the system working and route on real load signals.

- [ ] Prometheus scraping vLLM, gateway and GPU exporter
- [ ] Grafana dashboards for TTFT, TPOT, ITL, throughput, queue time, error rate, GPU memory
- [ ] Gateway summary metrics pushed to the dashboard through the control-plane API
- [ ] Custom endpoint picker scoring workers by queue depth and KV-cache usage
- [ ] Health-aware routing that excludes unhealthy workers
- [ ] Backpressure and load shedding with clean `429` / `503`
- [ ] Priority handling for key tiers

**Done when:** dashboards show live data under load and unhealthy workers get no new requests.

### Week 6: Multi-model routing and llm-d (simulator)

**Goal:** route by model capability, and get llm-d routing working without needing real GPU load.

- [ ] Deploy Qwen2.5-1.5B-Instruct-AWQ as a second model
- [ ] Routing rule for simple vs harder prompts, with a baseline comparison
- [ ] Install Gateway API Inference Extension CRDs and a gateway that supports it
- [ ] Deploy the llm-d inference simulator pods
- [ ] Install the llm-d Router (EPP) and create an `InferencePool`
- [ ] Send test traffic through the Gateway, `HTTPRoute` and `InferencePool`
- [ ] Verify failover when a simulator pod is removed
- [ ] Write ADR-004 (how llm-d fits next to the custom picker)

**Done when:** requests route through llm-d to simulator pods and failover works.
**Note:** check the current llm-d quickstart and pin the chart and image versions you use.

### Week 7: llm-d with real vLLM, autoscaling and chaos tests

**Goal:** real traffic through llm-d, plus resilience evidence.

- [ ] Point the `InferencePool` at real vLLM pods (two small replicas sharing the GPU, with memory utilization split)
- [ ] Locust benchmark: round-robin vs custom picker vs llm-d EPP
- [ ] Autoscaling on queue depth (KEDA or custom-metric HPA), within what the GPU allows
- [ ] Chaos tests: kill a worker mid-stream, restart the gateway, restart the agent
- [ ] Record recovery behavior and error rates
- [ ] Save all raw benchmark data and settings

**Done when:** each routing strategy has a benchmark run with full conditions and the chaos tests are documented.

### Week 8: Cloud deployment, documentation and demo

**Goal:** public, documented and demonstrable.

- [ ] `render.yaml` and deploy the control plane and gateway to Render
- [ ] Move the database to an external managed Postgres and add a scripted backup and restore test
- [ ] Deploy the dashboard (Vercel or Render static)
- [ ] GitHub Actions: tests, lint, image build, dependency and image scanning, deploy on merge
- [ ] Agent connects from your PC to the Render gateway and handles cold-start reconnection
- [ ] Dashboard shows worker status and a "waking up" state
- [ ] Finish `docs/architecture.md`, `docs/security.md`, `docs/benchmarks.md`
- [ ] Update the README validation table with only what has been verified
- [ ] Record a 2 to 3 minute demo video

**Done when:** a stranger can open the dashboard, read the README, and see the demo, and the README's claims all match what you ran.

## 5. Benchmark plan

| Comparison | Variable | Constant |
|---|---|---|
| Model size | 0.5B fp16 vs 1.5B AWQ | Prompt/output length, concurrency |
| Replicas | 1 vs 2 on the same GPU | Model, load |
| Routing | Round-robin vs custom vs llm-d EPP | Model, replicas, load |
| Model routing | Single model vs multi-model router | Prompt mix |

Run at 1, 5, 10 and 25 clients only where the GPU can sustain it. Record: GPU model and VRAM, driver and OS, vLLM version, model and revision, quantization, prompt and output length, warm-up and test duration, vLLM flags, and p50 and p95 TTFT, tokens per second and error rate.

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| 4 GB VRAM runs out | Smaller model, shorter context, lower `--gpu-memory-utilization`, AWQ model |
| WSL2 GPU or k3s GPU scheduling fails | Run vLLM in Docker, validate manifests on kind with a mock worker, state this in the README |
| Render sleeps or restarts | Reconnecting agent, "waking up" dashboard state, documented limits |
| Free Postgres expires | External managed free Postgres plus scripted backups |
| Render free service is only 512 MB RAM and 0.1 CPU | Lightweight dependencies, no heavy in-process work |
| llm-d needs more hardware than available | Validate routing with the simulator first, claim only what real runs support |
| Scope too wide | Cut order below |
| Unreliable benchmark claims | Fixed methodology, raw data saved, conditions always published |

## 7. Cut order if time runs short

Remove in this order, keeping everything above it:

1. Autoscaling
2. Priority queues
3. Multi-model routing
4. llm-d with real vLLM (keep the simulator result)
5. Kubernetes (fall back to Docker plus a mock-worker Helm validation)

Never cut: real vLLM streaming, the authenticated gateway, the worker agent, the Render deployment, benchmarks with conditions, and honest documentation.

## 8. Out of scope

Multi-GPU scaling, prefill/decode disaggregation, NIXL, Terraform, Argo CD, OpenTelemetry tracing, always-on public GPU inference.

## 9. Decision log

| ID | Decision | Status |
|---|---|---|
| ADR-001 | Custom FastAPI gateway | Planned (Week 1) |
| ADR-002 | Outbound WebSocket worker protocol | Planned (Week 3) |
| ADR-003 | Deployment tracking in the control plane | Planned (Week 4) |
| ADR-004 | llm-d next to the custom picker | Planned (Week 6) |

## 10. Weekly checklist

At the end of each week:

- [ ] Everything built is committed and CI is green
- [ ] `docs/versions.md` matches what is installed
- [ ] README validation table updated
- [ ] A short note on what broke and how it was fixed
- [ ] Next week's tasks reviewed and adjusted