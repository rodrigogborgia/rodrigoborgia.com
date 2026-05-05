from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Cargamos el archivo .env apenas inicia el módulo
load_dotenv()


@dataclass
class Settings:
    # --- OpenAI (Motor principal) ---
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_text_model: str = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")

    # --- Almacenamiento (Google Cloud Storage) ---
    gcp_credentials_path: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    gcs_bucket_name: str = os.getenv("GCS_BUCKET_NAME", "")
    gcs_upload_prefix: str = os.getenv("GCS_UPLOAD_PREFIX", "gemini-images")

    # --- Redes Sociales ---
    meta_access_token: str = os.getenv("META_ACCESS_TOKEN", "")
    meta_page_id: str = os.getenv("META_PAGE_ID", "")
    meta_instagram_business_account_id: str = os.getenv(
        "META_INSTAGRAM_BUSINESS_ACCOUNT_ID", ""
    )
    linkedin_access_token: str = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    linkedin_author_urn: str = os.getenv("LINKEDIN_AUTHOR_URN", "")

    # --- Varios ---
    # CORRECCIÓN: Usamos field y default_factory para evitar el error de mutable default
    frontend_origins: list[str] = field(
        default_factory=lambda: os.getenv(
            "FRONTEND_ORIGINS", "http://localhost:3000"
        ).split(",")
    )

    sheet_id: str = os.getenv("SHEET_ID", "")
    sheet_credentials_path: str = os.getenv("SHEET_CREDENTIALS_PATH", "")


# Instancia global para importar en otros archivos
settings = Settings()
