# Benchmarks

## Conditions
| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 2050, 4096 MiB |
| OS | Ubuntu 24.04.1 on WSL2 |
| vLLM | 0.34.0 |
| Model | Qwen/Qwen2.5-0.5B-Instruct (revision in versions.md) |
| vLLM flags | --max-model-len 2048 --gpu-memory-utilization 0.80 |
| Prompt | "Explain gravity in three sentences." (streaming) |
| max_tokens | 64 |
| Duration | 60 s per run |
| Gateway | single process, RATE_LIMIT_PER_MIN raised so it does not interfere |
| Load generator | Locust 2.47.0, running on the same machine |

TTFC is time to first streamed chunk. The first request of each run includes warm-up and shows up as the maximum.

## With think time (0.5 to 1.5 s between requests)
| Users | Req/s | TTFC p50 / p95 | Total p50 / p95 | Failures |
|---|---|---|---|---|
| 1 | | | | |
| 5 | 3.0 | 37 / 44 ms | 790 / 810 ms | 0 |
| 10 | | | | |
| 25 | about 14 | 48 / 58 ms | 900 / 940 ms | 0 |
| 50 | about 24 | 61 / 92 ms | 1100 / 1200 ms | 0 |
| 100 | about 37 | 120 / 220 ms | 1900 / 2100 ms | 0 |

## No think time, 50 users
| Path | Req/s | TTFC p50 / p95 | Total p50 / p95 | Failures |
|---|---|---|---|---|
| Direct to vLLM | 35.0 | 82 / 100 ms | 1500 / 1600 ms | 0 |
| Through gateway | 35.7 | 98 / 180 ms | 1500 / 1600 ms | 0 |

## Findings
- Throughput saturates at about 35 to 40 req/s for this workload on this machine.
- The saturated run was GPU-bound: nvidia-smi showed 99 to 100% GPU utilization.
- The gateway adds about 16 ms (median) and about 80 ms (p95) to time to first chunk, and no measurable change to throughput or total time.
- Locust shares the machine with vLLM and the gateway, so CPU contention may account for a small part of the measured latency.
- Under saturation, requests queue and latency rises, with no failures observed up to 100 users.
- Client disconnect: <fill in PASS or FAIL from disconnect_test.py>.