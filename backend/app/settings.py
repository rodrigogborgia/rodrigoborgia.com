from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Cargamos el archivo .env apenas inicia el módulo
load_dotenv()


@dataclass
class Settings:

    # --- OpenAI ---
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_text_model: str = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")

    # --- Google Cloud ---
    gcp_credentials_path: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    gcs_bucket_name: str = os.getenv("GCS_BUCKET_NAME", "")

    gcs_upload_prefix: str = os.getenv("GCS_UPLOAD_PREFIX", "gemini-images")

    # --- Meta ---
    meta_access_token: str = os.getenv("META_ACCESS_TOKEN", "")

    meta_page_id: str = os.getenv("META_PAGE_ID", "")

    meta_instagram_business_account_id: str = os.getenv(
        "META_INSTAGRAM_BUSINESS_ACCOUNT_ID", ""
    )

    # --- LinkedIn ---
    linkedin_access_token: str = os.getenv("LINKEDIN_ACCESS_TOKEN", "")

    linkedin_author_urn: str = os.getenv("LINKEDIN_AUTHOR_URN", "")

    # --- TikTok ---
    tiktok_client_key: str = os.getenv("TIKTOK_CLIENT_KEY", "")

    tiktok_client_secret: str = os.getenv("TIKTOK_CLIENT_SECRET", "")

    tiktok_redirect_uri: str = os.getenv("TIKTOK_REDIRECT_URI", "")

    # --- Frontend ---
    frontend_origins: list[str] = field(
        default_factory=lambda: os.getenv(
            "FRONTEND_ORIGINS", "http://localhost:3000"
        ).split(",")
    )

    # --- Sheets ---
    sheet_id: str = os.getenv("SHEET_ID", "")

    sheet_credentials_path: str = os.getenv("SHEET_CREDENTIALS_PATH", "")

    # --- YouTube ---
    youtube_creds_path: str = os.getenv(
        "YOUTUBE_CREDS_PATH",
        "/Users/rodrigoborgia/RB/rodrigoborgia.com/backend/config/youtube.json",
    )


settings = Settings()
