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

        # Pasamos los textos por separado a las nuevas columnas
        logger.log_post(
            titulo=payload.topic,
            red_social="BORRADOR (No publicado)",
            post_id="PENDIENTE",
            objeciones=payload.topic,
            fecha=fecha_hoy,
            resumen_linkedin=content.get("linkedin_post", "No generado"),
            resumen_instagram=content.get("instagram_post", "No generado"),
            url_imagen=result.get("image_url", ""),
        )

        return {
            "status": "success",
            "message": "Contenido generado y guardado en columnas separadas.",
        }
    except Exception as e:
        print(f"🔴 ERROR EN EL PROCESO:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
