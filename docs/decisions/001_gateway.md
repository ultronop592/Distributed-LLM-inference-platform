# ADR-001: Custom FastAPI gateway in front of vLLM

## Status
Accepted

## Context
vLLM exposes an OpenAI-compatible API with no authentication, per-caller limits or usage accounting. The platform needs those, plus a place to add routing and worker health logic later.

## Decision
Build a thin FastAPI gateway that authenticates API keys, rate limits per key, limits request size, proxies streaming responses, and records token usage from vLLM's usage data.

## Consequences
- Full control over routing, which the load-aware picker needs later.
- The gateway is one more service to run and test.
- The rate limiter is in memory, so it resets on restart and does not work across multiple gateway replicas. A shared store would be needed when scaling out.
- Usage is not recorded if a client disconnects before the final usage chunk arrives.
- Alternatives considered: Envoy or the Gateway API with the llm-d router. These are revisited in the llm-d phase and compared against this gateway.