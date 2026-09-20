# Ollama live-model validation

Date: 2026-09-20

This validation used the local Ollama server at `127.0.0.1:11434` and synthetic project
evidence. No production data or external API credential was used. Results are hardware-specific
smoke tests, not production-quality accuracy measurements.

## qwen3:4b quality checks

| Incident | Classification | Confidence | Citations | Supported hypotheses | Latency |
| --- | --- | --- | --- | ---: | ---: |
| Authentication failure | Correct | High | Valid | 1 or more | 152.14 s |
| Timeout | Correct | High | Valid | 1 | 108.27 s |

The 4B model produced incident-specific summaries tied to configuration, log, status, runbook,
and prior-incident evidence. Its latency is acceptable for a recorded portfolio demonstration
but slow for an interactive console on the current laptop.

## qwen3:1.7b five-scenario smoke test

| Incident | Classification | Accepted by safety gates | Latency |
| --- | --- | --- | ---: |
| Authentication failure | Correct | Yes | 59.48 s |
| Timeout | Correct | No | 67.89 s |
| Mapping error | Correct | Yes | 68.00 s |
| Invalid payload | Correct | Yes | 64.34 s |
| Duplicate transaction | Correct | Yes | 49.90 s |

The timeout output was rejected because it contained no supported hypothesis. A second run after
prompt tightening still contained no supported hypothesis, so the workflow returned
`confidence=insufficient`. The grounding gate was intentionally kept strict.

## Decision

- Use `qwen3:4b` for live portfolio demonstrations.
- Configure a 240-second local model timeout on this hardware.
- Keep `mock`/deterministic diagnosis as the default for repeatable tests.
- Do not use `qwen3:1.7b` as the quality baseline.
- Run all five cases with 4B before claiming a complete live-model benchmark.
