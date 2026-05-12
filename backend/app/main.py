from __future__ import annotations
import logging
import traceback
import os
from datetime import datetime
from typing import Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Tus módulos locales
from .settings import settings
from .content_orchestrator import build_orchestrator_from_env
from .sheet_logger import SheetLogger
from .youtube_manager import YouTubeManager

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Generador de Contenido BorgIA - ADS Strategy Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DATOS ---


class PublishDailyInput(BaseModel):
    topic: str


class TopicDiscoveryInput(BaseModel):
    search_terms: List[str]


# --- ENDPOINTS ---


@app.post("/api/discover-and-generate")
def discover_and_generate(payload: TopicDiscoveryInput):
    try:
        orchestrator = build_orchestrator_from_env()

        raw_list = payload.search_terms
        processed_terms = []

        for item in raw_list:
            parts = item.replace("\r", "").replace("\t", "\n").split("\n")
            processed_terms.extend([p.strip() for p in parts if p.strip()])

        if not processed_terms:
            return {"status": "error", "message": "No se detectaron términos."}

        print(f"📋 Limpieza exitosa: {len(processed_terms)} términos detectados.")

        prompt_seleccion = f"""
        Actúa como un experto en Estrategia de Ventas B2B y LinkedIn. 
        Analiza esta lista de términos de búsqueda de Google Ads:
        {processed_terms}
        
        Selecciona los 7 términos que tengan mayor potencial para crear contenido educativo...
        REGLA: Devuelve ÚNICAMENTE los 7 términos elegidos, uno por línea.
        """

        response = orchestrator.text_generator.client.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": prompt_seleccion}]
        )

        selected_topics = response.choices[0].message.content.strip().split("\n")
        selected_topics = [
            t.lstrip("0123456789.- ").strip() for t in selected_topics if t.strip()
        ][:7]

        print(f"🎯 Temas seleccionados: {selected_topics}")

        results = []
        for topic in selected_topics:
            orchestrator.run_daily_workflow(topic)
            results.append(topic)

        return {"status": "success", "temas_elegidos": results}
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

                if not ids_pub["url_video"] or "youtu" not in str(ids_pub["url_video"]):
                    try:
                        video_filename = f"prod_{int(datetime.now().timestamp())}.mp4"
                        local_video_path = (
                            orchestrator.video_manager.create_faceless_video(
                                txt_ln, "", video_filename
                            )
                        )
                        yt_id = yt_manager.upload_short(
                            local_video_path, titulo, f"{txt_ln}\n\n#MetodoBorgIA"
                        )
                        ids_pub["url_video"] = f"https://www.youtube.com/shorts/{yt_id}"
                        orchestrator.storage_manager.upload_file(
                            local_video_path, f"videos/{video_filename}"
                        )
                        if os.path.exists(local_video_path):
                            os.remove(local_video_path)
                            print(f"🧹 Temporal {video_filename} eliminado.")
                    except Exception as e:
                        print(f"❌ Error Video: {e}")

                if not ids_pub["li"] or ids_pub["li"] in ["N/A", ""]:
                    try:
                        res_ln = orchestrator.linkedin_publisher.publish_image_post(
                            txt_ln, img_url
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


@app.post("/api/update-metrics")
def update_metrics():
    """Actualiza likes y comentarios consultando las APIs reales."""
    try:
        orchestrator = build_orchestrator_from_env()
        sheet_logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)

        records = sheet_logger._worksheet.get_all_records()
        headers = [h.lower() for h in sheet_logger._worksheet.row_values(1)]
        updated_count = 0

        for i, row in enumerate(records, start=2):
            if str(row.get("estado", "")).lower() == "publicado":
                print(f"📊 Auditando: {row.get('titulo')}")

                # --- INSTAGRAM ---
                id_ig = row.get("id_instagram")
                if id_ig and id_ig not in ["", "N/A"]:
                    m_ig = orchestrator.meta_publisher.get_instagram_metrics(id_ig)
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("ig_likes") + 1, m_ig["likes"]
                    )
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("ig_comments") + 1, m_ig["comments"]
                    )

                # --- FACEBOOK ---
                id_fb = row.get("id_facebook")
                if id_fb and id_fb not in ["", "N/A"]:
                    m_fb = orchestrator.meta_publisher.get_facebook_metrics(id_fb)
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("fb_likes") + 1, m_fb["likes"]
                    )
                    sheet_logger._worksheet.update_cell(
                        i, headers.index("fb_comments") + 1, m_fb["comments"]
                    )

                # --- LINKEDIN ---
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


from fastapi.responses import PlainTextResponse


@app.get("/tiktok-verification-file.txt", response_class=PlainTextResponse)
def tiktok_verification():
    # Reemplaza 'CONTENIDO_DE_TU_ARCHIVO' por el código alfanumérico
    # que tiene adentro el archivo que descargaste de TikTok.
    return "tiktok-developers-site-verification=xhdjTftZXWTg65SToi0DEmVCODWB92S8"
