from __future__ import annotations
import json
import logging
import traceback
import os
import requests
from datetime import datetime
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Tus módulos locales
from .settings import settings
from .content_orchestrator import build_orchestrator_from_env
from .sheet_logger import SheetLogger
from .youtube_manager import YouTubeManager
from .style_brain import (
    merge_aprendizaje_with_diff_learning,
    build_system_prompt_for_generation,
    load_brain,
)
from openai import OpenAI

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Generador de Contenido BorgIA - ADS Strategy Edition", root_path="/backend"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/temp", StaticFiles(directory="temp"), name="temp")

# Ruta del archivo para el reporte de estado en Swagger
STATUS_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "temp", "publish_status.json"
)


def _normalize_sheet_records(records: List[Any], headers: List[str]) -> List[dict]:
    normalized = []
    for row in records:
        row_dict = {}
        for h in headers:
            row_dict[h] = row.get(h, "")
        normalized.append(row_dict)
    return normalized


def _update_status_tracker(
    current_action: str, processed: int, total: int, details: List[str]
):
    """Guarda el estado actual del script de fondo para que Swagger lo pueda leer."""
    try:
        os.makedirs(os.path.dirname(STATUS_FILE_PATH), exist_ok=True)
        status_data = {
            "status": "running" if processed < total or total == 0 else "completed",
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_action": current_action,
            "progress": f"{processed}/{total}",
            "logs": details[-15:],  # Guardamos los últimos 15 eventos para no saturar
        }
        with open(STATUS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"⚠️ No se pudo actualizar el archivo de estado: {e}")


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/", response_class=RedirectResponse)
def root_redirect():
    return "/backend/docs"


class TopicRequest(BaseModel):
    topic: str
    research: str


@app.post("/api/generate-post")
def generate_post(payload: TopicRequest):
    try:
        from .openai_client import OpenAIClient, OpenAITextGenerator

        client = OpenAIClient()
        generator = OpenAITextGenerator(client)

        with open(
            os.path.join(os.path.dirname(__file__), "programa_ventas.txt"),
            "r",
            encoding="utf-8",
        ) as f:
            metodologia = f.read()

        res = generator.generate_borgia_content(
            topic=payload.topic, research=payload.research, metodologia=metodologia
        )
        return json.loads(res["text"])
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/publish-pending")
async def publish_pending(background_tasks: BackgroundTasks):
    try:
        orchestrator = build_orchestrator_from_env()
        sheet_logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)

        def proceso_publicacion_background(orch, logger_sheet):
            details_log = []
            try:
                records = logger_sheet._worksheet.get_all_records()
                headers = [h.lower() for h in logger_sheet._worksheet.row_values(1)]
                yt_manager = YouTubeManager(settings.youtube_creds_path)

                # Filtrar cuántas filas reales tenemos que procesar
                filas_a_procesar = [
                    (idx, row)
                    for idx, row in enumerate(records, start=2)
                    if str(row.get("estado", "")).strip().lower()
                    in ["publicar", "publicado_parcial"]
                ]

                total_filas = len(filas_a_procesar)
                if total_filas == 0:
                    _update_status_tracker(
                        "No había filas pendientes de publicación.",
                        0,
                        0,
                        ["Fin del proceso autónomo."],
                    )
                    return

                _update_status_tracker(
                    "Iniciando bucle de publicación...", 0, total_filas, details_log
                )

                for processed_count, (i, row) in enumerate(filas_a_procesar, start=1):
                    titulo = row.get("titulo", "Sin Título")
                    msg = f"Procesando fila {i}: '{titulo}'"
                    details_log.append(msg)
                    _update_status_tracker(
                        msg, processed_count - 1, total_filas, details_log
                    )

                    txt_ln = row.get("linkedin_corregido") or row.get(
                        "resumen_linkedin"
                    )
                    txt_ig = row.get("instagram_corregido") or row.get(
                        "resumen_instagram"
                    )
                    img_url = row.get("url_imagen")

                    ids_pub = {
                        "li": row.get("id_linkedin"),
                        "ig": row.get("id_instagram"),
                        "fb": row.get("id_facebook"),
                        "url_video": row.get("url_video"),
                    }

                    # --- LÓGICA DE VIDEO (YouTube / TikTok) ---
                    if not ids_pub["url_video"] or "youtu" not in str(
                        ids_pub["url_video"]
                    ):
                        try:
                            msg_video = f"🎬 Creando video faceless para: {titulo}"
                            details_log.append(msg_video)
                            _update_status_tracker(
                                msg_video, processed_count - 1, total_filas, details_log
                            )

                            video_filename = (
                                f"prod_{int(datetime.now().timestamp())}.mp4"
                            )
                            local_video_path = orch.video_manager.create_faceless_video(
                                txt_ln, "", video_filename
                            )

                            url_video_almacenado = orch.storage_manager.upload_file(
                                local_video_path, f"videos/{video_filename}"
                            )

                            msg_yt = f"🚀 Subiendo Short a YouTube..."
                            details_log.append(msg_yt)
                            _update_status_tracker(
                                msg_yt, processed_count - 1, total_filas, details_log
                            )

                            yt_id = yt_manager.upload_short(
                                local_video_path, titulo, f"{txt_ln}\n\n#MetodoBorgIA"
                            )
                            ids_pub["url_video"] = (
                                f"https://www.youtube.com/shorts/{yt_id}"
                            )

                            if orch.tiktok_publisher:
                                try:
                                    msg_tt = "📱 Despachando a TikTok..."
                                    details_log.append(msg_tt)
                                    _update_status_tracker(
                                        msg_tt,
                                        processed_count - 1,
                                        total_filas,
                                        details_log,
                                    )
                                    caption_tt = (
                                        f"{titulo} #ventas #negociacion #MetodoBorgIA"
                                    )
                                    orch.tiktok_publisher.publish_video(
                                        local_video_path=local_video_path,
                                        title=caption_tt,
                                    )
                                except Exception as tte:
                                    details_log.append(f"❌ Falló TikTok: {str(tte)}")

                            if os.path.exists(local_video_path):
                                os.remove(local_video_path)

                        except Exception as ve:
                            details_log.append(f"❌ Error Video: {str(ve)}")

                    # --- REDES SOCIALES ---
                    if not ids_pub["li"] or ids_pub["li"] in ["N/A", ""]:
                        try:
                            res_ln = orch.linkedin_publisher.publish_text_post(txt_ln)
                            ids_pub["li"] = res_ln.get("id", "OK")
                        except Exception as e:
                            details_log.append(f"❌ Error LinkedIn: {str(e)}")

                    if not ids_pub["ig"]:
                        try:
                            res_ig = orch.meta_publisher.publish_to_meta(
                                txt_ig, img_url
                            )
                            ids_pub["ig"] = res_ig.get("id", "OK")
                        except Exception as e:
                            details_log.append(f"❌ Error Instagram: {str(e)}")

                    if not ids_pub["fb"]:
                        try:
                            res_fb = orch.meta_publisher.publish_to_facebook(
                                txt_ig, img_url
                            )
                            ids_pub["fb"] = res_fb.get("id", "OK")
                        except Exception as e:
                            details_log.append(f"❌ Error Facebook: {str(e)}")

                    todas_completas = all(
                        [
                            ids_pub["li"],
                            ids_pub["ig"],
                            ids_pub["fb"],
                            ids_pub["url_video"]
                            and "youtu" in str(ids_pub["url_video"]),
                        ]
                    )
                    nuevo_estado = (
                        "PUBLICADO" if todas_completas else "PUBLICADO_PARCIAL"
                    )
                    logger_sheet.update_after_publish(titulo, nuevo_estado, ids_pub)

                    if "url_video" in headers:
                        col_idx = headers.index("url_video") + 1
                        logger_sheet._worksheet.update_cell(
                            i, col_idx, ids_pub["url_video"]
                        )

                    details_log.append(f"✅ Finalizado post: {titulo}")
                    _update_status_tracker(
                        "Fila completada con éxito.",
                        processed_count,
                        total_filas,
                        details_log,
                    )

                _update_status_tracker(
                    "Todos los pendientes fueron procesados.",
                    total_filas,
                    total_filas,
                    details_log,
                )

            except Exception as bge:
                details_log.append(f"❌ Error fatal: {str(bge)}")
                _update_status_tracker(f"Error: {str(bge)}", 0, 0, details_log)

        background_tasks.add_task(
            proceso_publicacion_background, orchestrator, sheet_logger
        )

        return {
            "status": "success",
            "message": "Publicación iniciada. Consultá el estado actual desde el endpoint /api/publish-status",
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/publish-status")
def get_publish_status():
    """Permite ver el progreso actual del renderizado y publicación desde Swagger."""
    if not os.path.exists(STATUS_FILE_PATH):
        return {
            "status": "idle",
            "message": "No hay ningún proceso activo o registrado recientemente.",
        }
    try:
        with open(STATUS_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo el estado: {e}")


@app.get("/tiktok-verification-file.txt", response_class=PlainTextResponse)
def tiktok_verification():
    return "tiktok-developers-site-verification=xhdjTftZXWTg65SToi0DEmVCODWB92S8"
