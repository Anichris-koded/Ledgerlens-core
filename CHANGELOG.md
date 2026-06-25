# Changelog

All notable changes to `ledgerlens-core` are documented in this file.

## Unreleased

### Added
- Synthetic SDEX trade generator (`ingestion/synthetic_data.py`) with
  labelled wash-trading rings for local training and testing.
- Labelled training dataset builder (`detection/dataset.py`).
- SQLite-backed local `RiskScore` store (`detection/storage.py`).
- Local read-only FastAPI app (`api/main.py`) serving `/scores`, `/alerts`,
  and `/assets/risk-ranking`.
- `ledgerlens` CLI (`cli.py`): `generate-data`, `train`, `score`, `serve`.
- Retrying HTTP client for Horizon API calls (`ingestion/http_client.py`).
- Dockerfile, docker-compose, and GitHub Actions CI workflow.
- Kubernetes Helm chart (`helm/ledgerlens/`) with templates for API
  Deployment, Ingestion Worker, HPA, Service, Ingress, ConfigMap, Secret,
  PersistentVolumeClaim, and ServiceAccount. Liveness/readiness probes
  on the API deployment (`GET /health` and `/health/ready`).
  Documented in `docs/kubernetes_deployment.md`.
- Token-bucket rate limiter (`ingestion/rate_limiter.py`) with sync/async
  `acquire`, non-blocking `try_acquire`, and `set_rate`. Integrated into
  `HorizonStreamer` as an async SSE consumer class.
- `BackpressureController` that pauses SSE consumption when the downstream
  queue exceeds a configurable high-watermark (default 1000) and resumes at
  a low-watermark (default 500).
- `AdaptiveRateController` that halves the current rate on HTTP 429 and
  restores linearly over `RATE_RESTORE_SECONDS` (default 60).
- `HORIZON_RATE_LIMIT`, `HORIZON_RATE_BUCKET_CAPACITY`,
  `HORIZON_QUEUE_HIGH_WATERMARK`, `HORIZON_QUEUE_LOW_WATERMARK`,
  `RATE_RESTORE_SECONDS` configuration variables in `config/settings.py`.
- `GET /health/ready` readiness probe endpoint.
- `GET /stream/rate-limiter` admin-gated endpoint returning current rate,
  bucket level, backpressure state, and queue size.
- `ComplianceReportGenerator` (`detection/compliance_report.py`) producing
  self-contained HTML audit reports (and optional PDF via weasyprint) with
  executive summary, top-5 SHAP features with plain-English descriptions,
  Benford analysis, trade timeline, model version, and data provenance.
- `cli.py report generate --wallet G... --date YYYY-MM-DD --output report.html`
  subcommand for generating compliance audit reports.
- `cli.py completion --shell {bash,zsh,fish}` subcommand printing shell
  completion scripts. Documented in `docs/cli_reference.md`.

### Fixed
- `detection/shap_explainer.py` updated for the current SHAP `TreeExplainer`
  output shape.

## 0.1.0

- Initial scaffold: Horizon ingestion, Benford's Law engine, ML feature
  engineering, ensemble model training/inference, `RiskScore` schema.
