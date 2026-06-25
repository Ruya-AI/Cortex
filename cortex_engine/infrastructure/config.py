from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from cortex_engine.infrastructure.config_schema import QAConfig

logger = logging.getLogger(__name__)

_CONFIG_FILENAME = ".qa-config.yml"


def _resolve_env_vars(data):
    """Recursively resolve ${ENV_VAR} references in string values."""
    if isinstance(data, str):
        return re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.environ.get(m.group(1), m.group(0)),
            data,
        )
    if isinstance(data, dict):
        return {k: _resolve_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_vars(v) for v in data]
    return data


def load_config(repo_path: Path) -> QAConfig:
    config_file = repo_path / _CONFIG_FILENAME
    if not config_file.exists():
        logger.info("No %s found — using defaults", _CONFIG_FILENAME)
        return QAConfig()

    try:
        raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        logger.error("Failed to parse %s: %s", config_file, e)
        raise ValueError(f"Invalid YAML in {config_file}: {e}") from e

    if raw is None:
        return QAConfig()
    if not isinstance(raw, dict):
        raise ValueError(f"{config_file} must be a YAML mapping")

    resolved = _resolve_env_vars(raw)
    try:
        return QAConfig.model_validate(resolved)
    except ValidationError as e:
        logger.error("Config validation failed: %s", e)
        raise
