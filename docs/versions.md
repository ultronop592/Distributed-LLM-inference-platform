# Pinned versions

| Item | Version |
|---|---|
| OS | Ubuntu 24.04.1 LTS on WSL2 (kernel 5.15.167.4) |
| Python | 3.12 |
| GPU | NVIDIA GeForce RTX 2050, 4096 MiB |
| NVIDIA driver | 620.73.02 (CUDA 13.5 reported by nvidia-smi) |
| vLLM | 0.34.0 |
| torch | 2.14.0+cu130 |
| Model | Qwen/Qwen2.5-0.5B-Instruct |
| Model revision | <folder name from the snapshots command> |
| vLLM flags | --max-model-len 2048 --gpu-memory-utilization 0.80 |
| FastAPI | 0.165.0 |
| uvicorn | 0.54.0 |
| httpx | 0.28.1 |
| pydantic | 2.14.4 |
| pytest | 9.2.0 |

## Baseline (single request, no load)

| Measurement | Value |
|---|---|
| GPU memory used with model loaded | <MiB from nvidia-smi> |
| 64-token completion, direct to vLLM | <seconds, ignoring first run> |
| 64-token completion, through gateway | <seconds, ignoring first run> |