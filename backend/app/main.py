from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import traceback
from typing import Any
from datetime import datetime

from .settings import settings
from .content_orchestrator import build_orchestrator_from_env
from .sheet_logger import SheetLogger

app = FastAPI(title="Generador de Contenido BorgIA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PublishDailyInput(BaseModel):
    topic: str


@app.post("/api/publish-daily")
def publish_daily(payload: PublishDailyInput) -> dict[str, Any]:
    try:
        orchestrator = build_orchestrator_from_env()
        result = orchestrator.create_and_publish_daily_post(payload.topic)
        content = result["borgia_content"]

        logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Registramos con los nuevos campos vacíos para corrección futura
        logger.log_post(
            titulo=payload.topic,
            red_social="BORRADOR (No publicado)",
            post_id="PENDIENTE",
            objeciones=payload.topic,
            fecha=fecha_hoy,
            resumen_linkedin=content.get("linkedin_post", "No generado"),
            resumen_instagram=content.get("instagram_post", "No generado"),
            url_imagen=result.get("image_url", ""),
            linkedin_corregido="",
            instagram_corregido="",
        )

        return {
            "status": "success",
            "message": "Contenido generado y guardado para revisión.",
        }
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"🔴 ERROR EN EL PROCESO:\n{error_detail}")
        raise HTTPException(status_code=500, detail=str(e))
