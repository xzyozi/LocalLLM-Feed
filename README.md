# LocalLLM Feed 🦙

> **A daily TL;DR feed for local LLMs & GGUF models (GitHub Actions + GitHub Pages, zero infrastructure)**

[English](./README.md) | [日本語](./README.ja.md)

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live%20Demo-brightgreen?logo=github)](https://xzyozi.github.io/LocalLLM-Feed/)
[![CI](https://github.com/xzyozi/LocalLLM-Feed/actions/workflows/ci.yml/badge.svg)](https://github.com/xzyozi/LocalLLM-Feed/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

LocalLLM Feed collects GGUF model activity from Hugging Face daily and helps you discover and deploy the models that best fit your hardware (VRAM) and use case (speed vs. accuracy) with minimal noise.

🌐 **Live Demo**: https://xzyozi.github.io/LocalLLM-Feed/

## Features

- **Separation of facts and scoring**: the backend (GitHub Actions) extracts only facts such as parameter count, quantization formats, and distillation flag. Scoring is computed dynamically by the frontend (GitHub Pages).
- **Client-side dynamic scoring**: Total Score is recomputed and sorted in the browser based on your VRAM setting (no database or API server).
- **Export to your local environment**: one-click copy of Bash environment variables (with an auto-estimated `n_gpu_layers`) or an Ollama Modelfile for the selected model.
- **Zero infrastructure**: runs entirely on GitHub Actions and Pages, with no running cost.

## Architecture

```
Hugging Face API
      │ (once per day / GitHub Actions)
      ▼
Crawl (HuggingFaceCrawler) → TL;DR extraction (rule-based) → Feed build (FeedBuilder)
      │
      ▼
public/data/models_feed.json  ──(GitHub Pages)──▶  Browser (dynamic scoring, search, export)
```

See the design docs (in Japanese): [Basic Design](./docs/design/LLF-BD-001_基本設計書.md), [Detailed Design](./docs/design/LLF-DD-001_詳細設計書.md), [Data Structure](./docs/design/LLF-DS-001_データ構造仕様書.md), [Scoring Spec](./docs/design/LLF-SC-001_スコアリング設定仕様書.md).

## Configuration

Collection conditions and scoring weights are adjustable via TOML in `config/` (no code changes required).

- `config/collection.toml`: author allowlist, retention period, download threshold, popular-author scan settings.
- `config/scoring.toml`: per-VRAM-tier weights, quantization bonuses, `n_gpu_layers` estimation coefficients.

## Development

This project uses [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run the pipeline locally (accesses the HF API)
python -m localllm_feed.pipeline

# Lint, type-check, and test
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

The generated `public/data/models_feed.json` is served via GitHub Pages.

## License

[MIT](./LICENSE)