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
from fastapi.responses import RedirectResponse, PlainTextResponse
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


# ============================================================================
# HELPERS DE NORMALIZACIÓN
# ============================================================================


def _normalize_sheet_records(records: List[Any], headers: List[str]) -> List[dict]:
    """
    Se asegura de que cada fila devuelta por la API de Google Sheets sea un
    diccionario válido, incluso si vino como una lista cruda.
    """
    normalized = []
    for row in records:
        if isinstance(row, dict):
            # Ya es un diccionario, normalizamos las llaves a minúscula y sin espacios
            clean_row = {str(k).strip().lower(): v for k, v in row.items()}
            normalized.append(clean_row)
        elif isinstance(row, list):
            # Es una lista cruda, mapeamos según la posición de los headers
            row_dict = {}
            for idx, header in enumerate(headers):
                if idx < len(row):
                    row_dict[header] = row[idx]
                else:
                    row_dict[header] = ""
            normalized.append(row_dict)
        else:
            normalized.append({})
    return normalized


# ============================================================================
# MODELOS DE PETICIÓN (PYDANTIC)
# ============================================================================


class SyncBrainRequest(BaseModel):
    platform: str  # "linkedin" or "instagram"
    original_text: str
    corrected_text: str
    post_id: Optional[int] = None


class GenerateRequest(BaseModel):
    topic: str
    extra_instructions: Optional[str] = None


class TopicDiscoveryInput(BaseModel):
    search_terms: List[str]


# ============================================================================
# ENDPOINTS DEL CEREBRO DINÁMICO (Style Brain / Diff Learning)
# ============================================================================


@app.post("/api/sync-brain/batch")
def sync_brain_batch_from_posteador():
    """
    Lee la tabla Posteador directamente desde Google Sheets.
    Realiza Diff Learning para cada fila pendiente y marca como completada.
    """
    try:
        sheet_logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)
        client = OpenAI()

        # Leemos los datos crudos
        raw_values = sheet_logger._worksheet.get_all_values()
        if not raw_values:
            return {
                "ok": True,
                "message": "Planilla vacía",
                "stats": {"total_rows": 0, "processed": 0, "skipped": 0, "errors": 0},
            }

        headers = [str(h).strip().lower() for h in raw_values[0]]

        # gspread get_all_records() devuelve diccionarios omitiendo el header
        records = sheet_logger._worksheet.get_all_records()
        records = _normalize_sheet_records(records, headers)

        results = []
        processed_count = 0
        skipped_count = 0
        error_count = 0

        for row_idx, row in enumerate(records, start=2):
            # FILTRO 1: Verificar si Aprendizaje_Procesado está pendiente
            aprendizaje_val = str(row.get("aprendizaje_procesado", "")).strip().lower()
            if aprendizaje_val and aprendizaje_val not in ["false", "0", ""]:
                continue

            # FILTRO 2: Verificar que exista texto en columnas corregidas
            linkedin_orig = str(row.get("linkedin", "")).strip()
            linkedin_corr = str(row.get("linkedin_corregido", "")).strip()
            instagram_orig = str(row.get("instagram", "")).strip()
            instagram_corr = str(row.get("instagram_corregido", "")).strip()

            has_linkedin_correction = linkedin_orig and linkedin_corr
            has_instagram_correction = instagram_orig and instagram_corr

            if not (has_linkedin_correction or has_instagram_correction):
                skipped_count += 1
                results.append(
                    {
                        "row_idx": row_idx,
                        "status": "skipped",
                        "reason": "Sin textos corregidos (linkedin_corregido e instagram_corregido vacíos)",
                    }
                )
                continue

            # Procesar correcciones encontradas
            try:
                for platform, orig, corr in [
                    ("linkedin", linkedin_orig, linkedin_corr),
                    ("instagram", instagram_orig, instagram_corr),
                ]:
                    if not (orig and corr and orig.strip() != corr.strip()):
                        continue

                    new_aprendizaje = merge_aprendizaje_with_diff_learning(
                        original_text=orig,
                        corrected_text=corr,
                        platform=platform,
                        openai_client=client,
                        row_id=row_idx,
                    )

                    results.append(
                        {
                            "row_idx": row_idx,
                            "platform": platform,
                            "status": "success",
                            "aprendizaje_dinamico": new_aprendizaje,
                        }
                    )
                    processed_count += 1

                # MARCADO POST-PROCESAMIENTO: Actualizar Aprendizaje_Procesado
                timestamp = datetime.utcnow().isoformat() + "Z"
                try:
                    aprendizaje_col_idx = headers.index("aprendizaje_procesado") + 1
                    sheet_logger._worksheet.update_cell(
                        row_idx, aprendizaje_col_idx, timestamp
                    )
                    logger.info(
                        f"Fila {row_idx}: Aprendizaje_Procesado marcado como completado ({timestamp})"
                    )
                except ValueError:
                    logger.warning(
                        "No se encontró la columna 'aprendizaje_procesado' en los headers."
                    )

            except Exception as e:
                logger.error(f"Error procesando fila {row_idx}: {e}")
                error_count += 1
                results.append(
                    {
                        "row_idx": row_idx,
                        "status": "error",
                        "error": str(e),
                    }
                )

        return {
            "ok": True,
            "message": "Batch processing desde Posteador completado",
            "stats": {
                "total_rows": len(records),
                "processed": processed_count,
                "skipped": skipped_count,
                "errors": error_count,
            },
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error crítico en /api/sync-brain/batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-post")
def generate_post(payload: GenerateRequest):
    try:
        brain = load_brain()
        prompts = build_system_prompt_for_generation(
            topic=payload.topic,
            extra_instructions=payload.extra_instructions or "",
        )
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompts["system_prompt"]},
                {"role": "user", "content": prompts["user_prompt"]},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        content = (
            resp.choices[0].message.content
            if hasattr(resp.choices[0].message, "content")
            else resp.choices[0].message["content"]
        )

        reglas = brain.get("reglas_fijas", {})
        hashtags = reglas.get("hashtags_block", "")
        pd = reglas.get("pd", "")
        final = f"{content}\n\n{hashtags}\n{pd}"
        return {"ok": True, "post": final}
    except Exception as e:
        logger.error(f"Error en /api/generate-post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS DE SEGUNDO PLANO (Descubrimiento y Procesamiento)
# ============================================================================


@app.post("/api/discover-and-generate")
def discover_and_generate(
    payload: TopicDiscoveryInput, background_tasks: BackgroundTasks
):
    try:
        orchestrator = build_orchestrator_from_env()
        sheet_logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)

        processed_terms = []
        for item in payload.search_terms:
            parts = item.replace("\r", "").split("\n")
            processed_terms.extend([p.strip() for p in parts if p.strip()])

        if not processed_terms:
            return {"status": "error", "message": "No hay términos."}

        prompt = f"""
        Selecciona los 7 mejores temas de esta lista para publicar en LinkedIn B2B: {processed_terms}.
        Devuelve un objeto JSON con una única llave "temas" que contenga una lista de strings.
        Ejemplo: {{"temas": ["Tema 1", "Tema 2"]}}
        """

        res = orchestrator.text_generator.client.chat.completions.create(
            model=orchestrator.text_generator.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        data_temas = json.loads(res.choices[0].message.content)
        temas_elegidos = data_temas.get("temas", [])

        logging.info(f"🎯 Temas filtrados por OpenAI: {temas_elegidos}")

        # Función interna en segundo plano para evitar el timeout 504
        def procesar_en_segundo_plano(temas, logger_sheet):
            for t in temas:
                try:
                    logging.info(
                        f"🚀 [Background] Iniciando flujo completo para el tópico: '{t}'"
                    )
                    orchestrator.create_and_publish_daily_post(t, logger=logger_sheet)
                except Exception as ex:
                    logging.error(f"❌ Error en background procesando tema '{t}': {ex}")

        # Disparamos la tarea de fondo de FastAPI
        background_tasks.add_task(
            procesar_en_segundo_plano, temas_elegidos, sheet_logger
        )

        return {
            "status": "success",
            "message": "Procesamiento de temas iniciado en segundo plano exitosamente.",
            "temas_detectados": temas_elegidos,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/publish-pending")
async def publish_pending():
    try:
        orchestrator = build_orchestrator_from_env()
        sheet_logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)
        yt_manager = YouTubeManager(settings.youtube_creds_path)

        records = sheet_logger._worksheet.get_all_records()
        headers = [h.lower() for h in sheet_logger._worksheet.row_values(1)]

        processed_count = 0

        for i, row in enumerate(records, start=2):
            estado_original = str(row.get("estado", "")).strip().lower()

            if estado_original in ["publicar", "publicado_parcial"]:
                titulo = row.get("titulo", "Sin Título")
                print(f"🧐 Procesando fila {i}: {titulo}")

                txt_ln = row.get("linkedin_corregido") or row.get("resumen_linkedin")
                txt_ig = row.get("instagram_corregido") or row.get("resumen_instagram")
                img_url = row.get("url_imagen")

                ids_pub = {
                    "li": row.get("id_linkedin"),
                    "ig": row.get("id_instagram"),
                    "fb": row.get("id_facebook"),
                    "url_video": row.get("url_video"),
                }

                url_video_almacenado = None
                if not ids_pub["url_video"] or "youtu" not in str(ids_pub["url_video"]):
                    try:
                        video_filename = f"prod_{int(datetime.now().timestamp())}.mp4"
                        local_video_path = (
                            orchestrator.video_manager.create_faceless_video(
                                txt_ln, "", video_filename
                            )
                        )

                        # 1. Lo subimos a tu storage en la nube (S3/DigitalOcean Spaces)
                        url_video_almacenado = orchestrator.storage_manager.upload_file(
                            local_video_path, f"videos/{video_filename}"
                        )

                        # 2. Lo subimos a YouTube Shorts
                        yt_id = yt_manager.upload_short(
                            local_video_path, titulo, f"{txt_ln}\n\n#MetodoBorgIA"
                        )
                        ids_pub["url_video"] = f"https://www.youtube.com/shorts/{yt_id}"

                        # 🚀 3. NUEVO ORDEN: Subimos a TikTok usando el ARCHIVO LOCAL antes de borrarlo
                        if orchestrator.tiktok_publisher:
                            try:
                                caption_tt = (
                                    f"{titulo} #ventas #negociacion #MetodoBorgIA"
                                )
                                # Le pasamos local_video_path, igual que a YouTube
                                res_tt = orchestrator.tiktok_publisher.publish_video(
                                    local_video_path=local_video_path, title=caption_tt
                                )
                                if res_tt.get("status") == "success":
                                    print(f"✅ Video despachado a TikTok con éxito.")
                            except Exception as e:
                                print(
                                    f"❌ Error publicando en TikTok dentro de la cadena: {e}"
                                )

                        # 🧹 4. RECIÉN ACÁ BORRAMOS: Una vez que YouTube y TikTok tienen sus copias
                        if os.path.exists(local_video_path):
                            os.remove(local_video_path)
                            print(
                                f"🧹 Temporal {video_filename} eliminado de forma segura."
                            )

                    except Exception as e:
                        print(f"❌ Error Procesando Recurso de Video en cadena: {e}")

                if not ids_pub["li"] or ids_pub["li"] in ["N/A", ""]:
                    try:
                        res_ln = orchestrator.linkedin_publisher.publish_text_post(
                            txt_ln
                        )
                        ids_pub["li"] = res_ln.get("id", "OK")
                    except Exception as e:
                        print(f"❌ Error LinkedIn: {e}")

                if not ids_pub["ig"]:
                    try:
                        res_ig = orchestrator.meta_publisher.publish_to_meta(
                            txt_ig, img_url
                        )
                        ids_pub["ig"] = res_ig.get("id", "OK")
                    except Exception as e:
                        print(f"❌ Error Instagram: {e}")

                if not ids_pub["fb"]:
                    try:
                        res_fb = orchestrator.meta_publisher.publish_to_facebook(
                            txt_ig, img_url
                        )
                        ids_pub["fb"] = res_fb.get("id", "OK")
                    except Exception as e:
                        print(f"❌ Error Facebook: {e}")

                todas_completas = all(
                    [
                        ids_pub["li"],
                        ids_pub["ig"],
                        ids_pub["fb"],
                        ids_pub["url_video"] and "youtu" in str(ids_pub["url_video"]),
                    ]
                )
                nuevo_estado = "PUBLICADO" if todas_completas else "PUBLICADO_PARCIAL"
                sheet_logger.update_after_publish(titulo, nuevo_estado, ids_pub)

                if "url_video" in headers:
                    col_idx = headers.index("url_video") + 1
                    sheet_logger._worksheet.update_cell(
                        i, col_idx, ids_pub["url_video"]
                    )

                processed_count += 1

        return {"status": "success", "detalle": f"Procesados: {processed_count}"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS DE INTEGRACIÓN Y MÉTRICAS
# ============================================================================


@app.get("/api/v1/auth/tiktok/login")
def tiktok_login():
    client_key = os.getenv("TIKTOK_CLIENT_KEY", "")
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI", "")
    scopes = "user.info.basic,video.publish,video.upload"

    tiktok_url = (
        f"https://www.tiktok.com/v2/auth/authorize/?"
        f"client_key={client_key}"
        f"&scope={scopes}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
    )
    return RedirectResponse(url=tiktok_url)


@app.get("/api/v1/auth/tiktok/callback")
def tiktok_callback(code: str = None, error: str = None):
    if error:
        return {"status": "error", "message": error}

    token_url = "https://open.tiktokapis.com/v2/oauth/token/"
    payload = {
        "client_key": settings.tiktok_client_key,
        "client_secret": settings.tiktok_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.tiktok_redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        response = requests.post(token_url, data=payload, headers=headers, timeout=20)
        data = response.json()
        access_token = data.get("access_token")

        if response.status_code == 200 and access_token:
            with open("tiktok_tokens.json", "w") as f:
                json.dump(data, f, indent=2)
            return {
                "status": "success",
                "access_token_preview": access_token[:20] + "...",
                "open_id": data.get("open_id"),
                "scope": data.get("scope"),
            }
        return {"status": "error", "details": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/update-metrics")
def update_metrics():
    try:
        orchestrator = build_orchestrator_from_env()
        sheet_logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)

        records = sheet_logger._worksheet.get_all_records()
        headers = [h.lower() for h in sheet_logger._worksheet.row_values(1)]
        updated_count = 0

        for i, row in enumerate(records, start=2):
            if str(row.get("estado", "")).lower() == "publicado":
                id_ig = row.get("id_instagram")
                if id_ig and id_ig not in ["", "N/A"]:
                    m_ig = orchestrator.meta_publisher.get_instagram_metrics(id_ig)
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("ig_likes") + 1, m_ig["likes"]
                    )
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("ig_comments") + 1, m_ig["comments"]
                    )

                id_fb = row.get("id_facebook")
                if id_fb and id_fb not in ["", "N/A"]:
                    m_fb = orchestrator.meta_publisher.get_facebook_metrics(id_fb)
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("fb_likes") + 1, m_fb["likes"]
                    )
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("fb_comments") + 1, m_fb["comments"]
                    )

                id_li = row.get("id_linkedin")
                if id_li and id_li not in ["", "N/A"]:
                    m_li = orchestrator.linkedin_publisher.get_metrics(id_li)
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("li_likes") + 1, m_li["likes"]
                    )
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("li_comments") + 1, m_li["comments"]
                    )

                updated_count += 1

        return {"status": "success", "message": f"Sincronizadas {updated_count} filas."}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/test-video")
def test_video(topic: str):
    try:
        orchestrator = build_orchestrator_from_env()
        sheet_logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)
        cell = sheet_logger._worksheet.find(topic)
        if not cell:
            return {"error": "Tópico no encontrado"}

        row_data = sheet_logger._worksheet.row_values(cell.row)
        headers = [h.lower() for h in sheet_logger._worksheet.row_values(1)]
        row_dict = dict(zip(headers, row_data))
        script = row_dict.get("linkedin_corregido") or row_dict.get("resumen_linkedin")

        path = orchestrator.video_manager.create_faceless_video(
            text_script=script,
            image_path="",
            output_path=f"test_{int(datetime.now().timestamp())}.mp4",
        )
        url = orchestrator.storage_manager.upload_file(path, f"videos/test_{topic}.mp4")
        if os.path.exists(path):
            os.remove(path)
        return {"status": "success", "video_url": url}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tiktok-verification-file.txt", response_class=PlainTextResponse)
def tiktok_verification():
    return "tiktok-developers-site-verification=xhdjTftZXWTg65SToi0DEmVCODWB92S8"


@app.get("/api/test-tiktok")
def test_tiktok():
    try:
        orchestrator = build_orchestrator_from_env()
        local_video_path = "temp/Estoy concediendo, no negociando.mp4"

        if not orchestrator.tiktok_publisher:
            return {"status": "error", "message": "TikTokPublisher no inicializado"}

        res_tt = orchestrator.tiktok_publisher.publish_video(
            local_video_path=local_video_path,
            title="Estoy concediendo, no negociando #MetodoBorgIA",
        )
        return {"status": "success", "tiktok_result": res_tt}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
