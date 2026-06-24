# Changelog

All notable changes to `ledgerlens-core` are documented in this file.

## Unreleased

### Added
- **Stateful rolling-window streaming scorer** (issue #152): `detection/rolling_window.py`
  introduces `WalletWindow` (per-wallet deque with 24-h eviction and 10 000-trade memory cap)
  and `RollingWindowState` / `RollingWindowStore` (SQLite checkpoint persistence).
- `FeatureEngineering.compute_incremental()` computes the full feature vector from
  1 h / 4 h / 24 h rolling-window trade lists without replaying full trade history.
- `IncrementalScorer` in `detection/model_inference.py` wraps the rolling window,
  feature engineering, and model inference; emits a `RiskScore` only when the new
  score differs from the last emitted score by ≥ `STREAM_SCORE_DELTA_THRESHOLD` points.
- `cli.py stream` extended with `--checkpoint-interval` / `STREAM_CHECKPOINT_INTERVAL`
  and `--score-delta` / `STREAM_SCORE_DELTA_THRESHOLD` options; graceful SIGTERM/SIGINT
  shutdown writes a final checkpoint before exiting.
- `GET /stream/status` API endpoint returning `trades_per_second` (rolling 60-second
  average), `active_wallets`, and `last_trade_at`.
- `STREAM_CHECKPOINT_INTERVAL`, `STREAM_SCORE_DELTA_THRESHOLD`, `STREAM_WINDOW_HOURS`
  config vars added to `config/settings.py` and `.env.example`.
- SQLite migration 13: `rolling_window_checkpoints` table.
- `docs/streaming_scorer.md`: architecture, window management, delta threshold
  rationale, checkpoint strategy, graceful shutdown, and stream status API.

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

### Fixed
- `detection/shap_explainer.py` updated for the current SHAP `TreeExplainer`
  output shape.

## 0.1.0

- Initial scaffold: Horizon ingestion, Benford's Law engine, ML feature
  engineering, ensemble model training/inference, `RiskScore` schema.
