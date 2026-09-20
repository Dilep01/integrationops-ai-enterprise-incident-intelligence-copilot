# Portfolio claim verification

Verified locally on 2026-09-20.

| Claim | Evidence or command | Result |
| --- | --- | --- |
| Backend tests | `pytest` | 45 passed |
| Python coverage | `pytest --cov=integrationops --cov=integration_runtime --cov-fail-under=90` | 91.80% |
| Python lint | `ruff check .` | Passed |
| Offline gates | `integrationops-evaluate --enforce` | Passed |
| Real-model retrieval | `docs/evaluation/rag-live-validation.md` | Recall@K 1.0000, MRR 1.0000, diversity 1.0000, duplicate rate 0, ACL failures 0 |
| Frontend type safety | `npm run typecheck` in `apps/web` | Passed |
| Frontend production build | `npm run build` in `apps/web` | Passed |
| JavaScript dependency audit | `npm audit` in `apps/web` | 0 vulnerabilities |
| Database migrations | upgrade, check, downgrade, re-upgrade | Passed |
| Compose definition | `docker compose config --quiet` | Passed |
| Local LLM | `docs/evaluation/ollama-live-validation.md` | qwen3:4b authentication and timeout outputs accepted with valid citations |

## Scope notes

- The retrieval evaluation has 10 synthetic cases.
- The offline diagnosis fixture has 16 synthetic cases.
- The reported coverage is for the Python packages, not the React UI.
- The local model timings are specific to the development laptop.
- GitHub Actions is configured; the repository Actions page is the source for the latest remote result.
- No production connector, external customer data, or paid model API was used.
