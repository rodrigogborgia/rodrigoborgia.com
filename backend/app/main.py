from __future__ import annotations
import json
import logging
import traceback
import os
import requests
from datetime import datetime
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException
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
# ENDPOINTS DEL CEREBRO DINÁMICO (Style Brain / Diff Learning)
# ============================================================================


class SyncBrainRequest(BaseModel):
    """
    Sync Brain usando Diff Learning.
    Recibe el texto original (AI-generated) y el corregido (user-edited).
    Analiza QUÉ cambió para aprender el estilo.
    """

    platform: str  # "linkedin" or "instagram"
    original_text: str  # Texto original generado por IA
    corrected_text: str  # Texto corregido por Rodrigo
    post_id: Optional[int] = None  # Referencia a la fila Posteador (opcional)


@app.post("/api/sync-brain")
def sync_brain(payload: SyncBrainRequest):
    """
    Endpoint que recibe un post original + corregido.
    Realiza Diff Learning (análisis comparativo) para extraer patrones de estilo.
    Actualiza instrucciones_evolutivas.json con el aprendizaje.

    En producción, este endpoint estaría vinculado a:
    - Tabla Posteador: filas donde linkedin_corregido o instagram_corregido existan.
    - Campo Aprendizaje_Procesado: se marca como completado tras actualizar el JSON.
    """
    if not payload.original_text or not payload.corrected_text:
        raise HTTPException(
            status_code=400,
            detail="original_text y corrected_text son requeridos",
        )

    if payload.original_text.strip() == payload.corrected_text.strip():
        return {
            "ok": True,
            "message": "Sin cambios detectados. Aprendizaje no actualizado.",
            "post_id": payload.post_id,
        }

    try:
        client = OpenAI()
        new_aprendizaje = merge_aprendizaje_with_diff_learning(
            original_text=payload.original_text,
            corrected_text=payload.corrected_text,
            platform=payload.platform,
            openai_client=client,
            row_id=payload.post_id,
        )
        return {
            "ok": True,
            "aprendizaje_dinamico": new_aprendizaje,
            "post_id": payload.post_id,
            "message": "Cerebro actualizado con nuevo aprendizaje via Diff Learning",
        }
    except Exception as e:
        logger.error(f"Error en /api/sync-brain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SyncBrainBatchRequest(BaseModel):
    """
    Preparación para procesar lotes desde la tabla Posteador.
    Cada item contiene: platform, original, corregido e id de la fila.
    """

    posts: List[SyncBrainRequest]  # Lista de posts a procesar


def _normalize_sheet_records(records: list, headers: list) -> list:
    """Convierte filas de Sheets a diccionarios con llaves normalizadas."""
    normalized = []
    for row in records:
        if isinstance(row, dict):
            normalized.append({str(k).strip().lower(): v for k, v in row.items()})
        elif isinstance(row, (list, tuple)):
            normalized.append(
                {
                    headers[i].strip().lower(): row[i] if i < len(row) else ""
                    for i in range(len(headers))
                }
            )
        else:
            normalized.append({})
    return normalized


@app.post("/api/sync-brain/batch")
def sync_brain_batch_from_posteador():
    """
    Lee la tabla Posteador directamente desde Google Sheets.
    Filtra filas donde:
      - Aprendizaje_Procesado esté vacío/NULL/False
      - Y exista texto en linkedin_corregido O instagram_corregido
    Realiza Diff Learning para cada fila y marca como completada.

    Este endpoint está diseñado para ser invocado por un Cron Job.
    Respuesta incluye resumen de procesamiento (success/skipped/error) por fila.
    """
    try:
        sheet_logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)
        client = OpenAI()
        records = sheet_logger._worksheet.get_all_records()
        headers = [h.strip().lower() for h in sheet_logger._worksheet.row_values(1)]
        records = _normalize_sheet_records(records, headers)

        results = []
        processed_count = 0
        skipped_count = 0
        error_count = 0

        for row_idx, row in enumerate(
            records, start=2
        ):  # Row index starts at 2 (header is row 1)
            # FILTRO 1: Verificar si Aprendizaje_Procesado está pendiente
            aprendizaje_val = str(row.get("aprendizaje_procesado", "")).strip().lower()
            if aprendizaje_val and aprendizaje_val not in ["false", "0", ""]:
                # Ya fue procesada, saltala
                continue

            # FILTRO 2: Verificar que exista texto en columnas corregidas
            linkedin_orig = str(row.get("linkedin", "")).strip()
            linkedin_corr = str(row.get("linkedin_corregido", "")).strip()
            instagram_orig = str(row.get("instagram", "")).strip()
            instagram_corr = str(row.get("instagram_corregido", "")).strip()

            has_linkedin_correction = linkedin_orig and linkedin_corr
            has_instagram_correction = instagram_orig and instagram_corr

            if not (has_linkedin_correction or has_instagram_correction):
                # No hay textos corregidos para procesar
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

                    # Ejecutar Diff Learning
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
                aprendizaje_col_idx = (
                    headers.index("aprendizaje_procesado") + 1
                    if "aprendizaje_procesado" in headers
                    else None
                )

                if aprendizaje_col_idx:
                    sheet_logger._worksheet.update_cell(
                        row_idx, aprendizaje_col_idx, timestamp
                    )
                    logger.info(
                        f"Fila {row_idx}: Aprendizaje_Procesado marcado como completado ({timestamp})"
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


class GenerateRequest(BaseModel):
    topic: str
    extra_instructions: Optional[str] = None


@app.post("/api/generate-post")
def generate_post(payload: GenerateRequest):
    """
    Genera un post usando el aprendizaje dinámico actual.
    Inyecta las reglas_fijas y aprendizaje_dinamico en el System Prompt.
    """
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
        # Append fixed hashtags and PD to guarantee presence
        reglas = brain.get("reglas_fijas", {})
        hashtags = reglas.get("hashtags_block", "")
        pd = reglas.get("pd", "")
        final = f"{content}\n\n{hashtags}\n{pd}"
        return {"ok": True, "post": final}
    except Exception as e:
        logger.error(f"Error en /api/generate-post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS EXISTENTES (Descubrimiento, Publicación, etc.)
# ============================================================================


class TopicDiscoveryInput(BaseModel):
    search_terms: List[str]


@app.post("/api/discover-and-generate")
def discover_and_generate(payload: TopicDiscoveryInput):
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

        import json

        data_temas = json.loads(res.choices[0].message.content)
        temas_elegidos = data_temas.get("temas", [])

        logging.info(f"🎯 Temas filtrados y limpios: {temas_elegidos}")

        for t in temas_elegidos:
            logging.info(f"🚀 Iniciando flujo completo para el tópico: '{t}'")
            orchestrator.create_and_publish_daily_post(t, logger=sheet_logger)

        return {"status": "success", "temas_procesados": temas_elegidos}
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

                # --- GENERACIÓN DE VIDEO INTEGRADO ---
                url_video_almacenado = None
                if not ids_pub["url_video"] or "youtu" not in str(ids_pub["url_video"]):
                    try:
                        video_filename = f"prod_{int(datetime.now().timestamp())}.mp4"
                        local_video_path = (
                            orchestrator.video_manager.create_faceless_video(
                                txt_ln, "", video_filename
                            )
                        )

                        # Subimos el archivo a GCS para tener una URL fija accesible por TikTok
                        url_video_almacenado = orchestrator.storage_manager.upload_file(
                            local_video_path, f"videos/{video_filename}"
                        )

                        # Subida tradicional a YouTube Shorts
                        yt_id = yt_manager.upload_short(
                            local_video_path, titulo, f"{txt_ln}\n\n#MetodoBorgIA"
                        )
                        ids_pub["url_video"] = f"https://www.youtube.com/shorts/{yt_id}"

                        if os.path.exists(local_video_path):
                            os.remove(local_video_path)
                            print(f"🧹 Temporal {video_filename} eliminado.")
                    except Exception as e:
                        print(f"❌ Error Procesando Recurso de Video: {e}")

                # --- PUBLICACIÓN EN TIKTOK ---
                # Si el orquestador tiene las llaves de TikTok y logramos la URL en GCS
                if orchestrator.tiktok_publisher and url_video_almacenado:
                    try:
                        caption_tt = f"{titulo} #ventas #negociacion #MetodoBorgIA"
                        res_tt = orchestrator.tiktok_publisher.publish_video(
                            video_url=url_video_almacenado, title=caption_tt
                        )
                        if res_tt.get("status") == "success":
                            print(
                                f"✅ Video despachado a TikTok. ID: {res_tt.get('publish_id')}"
                            )
                    except Exception as e:
                        print(f"❌ Error publicando en TikTok: {e}")

                # --- REDES TRADICIONALES ---
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


@app.get("/api/v1/auth/tiktok/login")  # <-- Cambiado de .post a .get
def tiktok_login():
    """Redirige a la interfaz de consentimiento de TikTok."""
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

        print("\n🎯 TikTok RESPONSE:")
        print(data)

        access_token = data.get("access_token")

        if response.status_code == 200 and access_token:

            print("\n" + "🔑" * 20)
            print("TIKTOK ACCESS TOKEN:")
            with open("tiktok_tokens.json", "w") as f:
                json.dump(data, f, indent=2)
            print("🔑" * 20 + "\n")

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
                print(f"📊 Auditando: {row.get('titulo')}")

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


@app.post("/api/sync-brain")
def sync_brain():
    try:
        orchestrator = build_orchestrator_from_env()
        sheet_logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)
        orchestrator.sync_borgia_brain(sheet_logger)
        resumen = orchestrator.consolidate_knowledge()
        return {
            "status": "success",
            "mensaje": "Cerebro actualizado y consolidado",
            "esencia_actual": resumen,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/test-tiktok")
def test_tiktok():

    try:

        orchestrator = build_orchestrator_from_env()

        local_video_path = "temp/Estoy concediendo, no negociando.mp4"

        print("🎬 Probando upload TikTok...")
        print(local_video_path)

        if not orchestrator.tiktok_publisher:

            return {
                "status": "error",
                "message": "TikTokPublisher no inicializado",
            }

        res_tt = orchestrator.tiktok_publisher.publish_video(
            local_video_path=local_video_path,
            title="Estoy concediendo, no negociando #MetodoBorgIA",
        )

        print("🎯 RESULTADO TIKTOK:")
        print(res_tt)

        return {
            "status": "success",
            "tiktok_result": res_tt,
        }

    except Exception as e:

        traceback.print_exc()

        return {
            "status": "error",
            "message": str(e),
        }
