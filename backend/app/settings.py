from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_env_files() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    local_env_file = backend_dir / ".env"
    external_env_file = Path.home() / ".rb-secrets" / "backend.env"

    custom_env_file_raw = os.getenv("RB_ENV_FILE", "").strip()
    custom_env_file = Path(custom_env_file_raw).expanduser() if custom_env_file_raw else None

    candidate_files: list[Path] = []
    if custom_env_file:
        candidate_files.append(custom_env_file)
    candidate_files.extend([external_env_file, local_env_file])

    for env_file in candidate_files:
        if env_file.exists():
            load_dotenv(env_file, override=False)


_load_env_files()


@dataclass(frozen=True)
class Settings:
    brevo_api_key: str = os.getenv("BREVO_API_KEY", "")
    frontend_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "https://rodrigoborgia.com",
        ).split(",")
        if origin.strip()
    )


settings = Settings()
