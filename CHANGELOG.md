# Changelog

All notable changes to `ledgerlens-core` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are automated via [release-please](https://github.com/google-github-actions/release-please-action);
merging a release PR (created by the `release-please` GitHub Action) tags the
commit, generates this file, and publishes a tagged Docker image to GHCR.

## Unreleased

### Added
- **#143** `SorobanPublisher` half-open circuit breaker state machine (`detection/soroban_publisher.py`): transitions `open → half-open` after `SOROBAN_CIRCUIT_RESET_SECONDS`; probe success → `closed`; probe failure → `open` (timer reset); manual `reset_circuit()` closes immediately.
- **#143** `SorobanHealthStatus` dataclass and `SorobanPublisher.health()` / `reset_circuit()` methods for observable circuit state.
- **#143** `soroban_dead_letters` SQLite table (migration 14): open-circuit submissions written as `pending` DLQ rows instead of silently dropped.
- **#143** `SorobanPublisher._write_dead_letter()` persists failed submissions to DLQ; prunes to `SOROBAN_DLQ_MAX_ROWS`.
- **#143** `GET /admin/soroban/health`, `POST /admin/soroban/reset` (rate-limited 10/min), `GET /admin/soroban/dead-letters` admin-key-gated API endpoints (`api/admin_router.py`).
- **#143** `cli.py dlq-replay` command: replays pending DLQ items oldest-first, marks `replayed`/`failed`, supports `--dry-run` and `--limit`.
- **#143** `SOROBAN_DLQ_MAX_ROWS` env var in `.env.example`.
- **#143** `docs/soroban_operations.md`: circuit breaker states, health endpoint interpretation, DLQ replay procedure, manual reset runbook.

### Added
- **#147** Pedersen commitment ZK scheme (`detection/zk_commitment.py`): `PedersenParams`, `PedersenCommitment`, `ThresholdProof` dataclasses; `commit()`, `open()`, `prove_below_threshold()`, `verify_below_threshold()` functions over BN254 for privacy-preserving score attestation.
- **#147** API endpoints `POST /scores/{wallet}/commit` and `POST /scores/verify-threshold` for ZK threshold proofs.
- **#150** Full governance proposal engine (`detection/governance.py`): `GovernanceEngine` with `submit_proposal`, `cast_vote`, `tally_proposal`, `close_proposal`, `execute_proposal`, `close_expired`; `SettingsReloader` with compile-time allowlist and atomic `.env` write.
- **#150** SQLite migration 13: `governance_proposals`, `governance_votes`, `governance_committee` tables.
- **#150** Governance REST endpoints: `POST/GET /governance/proposals`, `GET /governance/proposals/{id}`, `POST /governance/proposals/{id}/vote`, `POST /governance/proposals/{id}/execute` (admin-key gated).
- **#150** `cli.py governance-close-expired` command.
- `docs/governance_protocol.md` updated to reflect full implemented lifecycle.

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
- `ledgerlens --version` / `-V` flag that reports the current version from
  `pyproject.toml`.
- `release-please` GitHub Action workflow for automated semantic versioning,
  changelog generation, and Docker image publishing to GHCR.

### Fixed
- `detection/shap_explainer.py` updated for the current SHAP `TreeExplainer`
  output shape.

## 0.1.0

- Initial scaffold: Horizon ingestion, Benford's Law engine, ML feature
  engineering, ensemble model training/inference, `RiskScore` schema.
