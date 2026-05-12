from __future__ import annotations
from typing import Any, Dict, Optional
import json
import logging
import os
from datetime import datetime
from backend.app.storage_manager import StorageManager
from backend.app.social_publisher import MetaSocialPublisher, LinkedInPublisher
from backend.app.openai_client import (
    OpenAIClient,
    OpenAITextGenerator,
    OpenAIImageGenerator,
)
from backend.app.search_client import SearchClient

# Importamos el nuevo gestor de video
from backend.app.video_manager import VideoManager


class ContentOrchestrator:
    def __init__(
        self,
        text_generator: OpenAITextGenerator,
        image_generator: OpenAIImageGenerator,
        search_client: SearchClient,
        storage_manager: StorageManager,
        meta_publisher: Optional[MetaSocialPublisher] = None,
        linkedin_publisher: Optional[LinkedInPublisher] = None,
        video_manager: Optional[VideoManager] = None,
    ) -> None:
        self.text_generator = text_generator
        self.image_generator = image_generator
        self.search_client = search_client
        self.storage_manager = storage_manager
        self.meta_publisher = meta_publisher
        self.linkedin_publisher = linkedin_publisher
        self.video_manager = video_manager

    def run_daily_workflow(self, topic: str) -> Dict[str, Any]:
        from backend.app.sheet_logger import SheetLogger
        from backend.app.settings import settings

        logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)
        print(f"🤖 Generando investigación y borradores para: {topic}")
        return self.create_and_publish_daily_post(topic, logger)

    def generate_video_script(self, original_text: str) -> str:
        """Destila el post de LinkedIn en un guion corto para video faceless."""
        prompt = f"""
        Actúa como un experto en copywriting B2B. Basado en este post de LinkedIn:
        '{original_text}'
        
        Crea un guion para un video faceless de 40 segundos máximo.
        REGLAS:
        1. Tono serio, autoritario y provocador (Método Borgia).
        2. Frases cortas e impactantes. 
        3. Sin hashtags ni despedidas largas.
        4. Máximo 120 palabras.
        """
        # Usamos el generador de texto existente
        res = self.text_generator.client.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()

    def dispatch_ready_posts(self, logger=None, pendientes=None) -> Dict[str, Any]:
        if not logger:
            from backend.app.sheet_logger import SheetLogger
            from backend.app.settings import settings

            logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)

        if pendientes is None:
            pendientes = logger.get_pending_publications()

        if not pendientes:
            print("ℹ️ No hay nada marcado como 'publicar' en el Excel.")
            return {"status": "nothing_to_publish"}

        results = []
        for post in pendientes:
            titulo = post.get("titulo", "Sin título")
            # Texto corregido es la prioridad
            txt_linkedin = post.get("linkedin_corregido") or post.get(
                "resumen_linkedin"
            )
            txt_social = post.get("instagram_corregido") or post.get(
                "resumen_instagram"
            )
            img_url = post.get("url_imagen")

            print(f"🚀 Procesando video y publicación para '{titulo}'...")

            # --- NUEVA LÓGICA DE VIDEO ---
            video_url_final = post.get("url_video")
            if not video_url_final and txt_linkedin:
                try:
                    # 1. Generar guion destilado
                    v_script = self.generate_video_script(txt_linkedin)

                    # 2. Descargar imagen localmente para procesar video
                    local_img = self.storage_manager.download_file(
                        img_url, "temp_bg.png"
                    )

                    # 3. Crear video
                    output_v = f"video_{datetime.now().strftime('%H%M%S')}.mp4"
                    local_video = self.video_manager.create_faceless_video(
                        v_script, local_img, output_v
                    )

                    # 4. Subir video a GCS
                    video_url_final = self.storage_manager.upload_file(
                        local_video, f"videos/{output_v}"
                    )
                    print(f"✅ Video Faceless generado: {video_url_final}")

                    # Limpiar locales
                    os.remove(local_img)
                    os.remove(local_video)
                except Exception as e:
                    print(f"⚠️ Error generando video: {e}")

            # --- PUBLICACIÓN ---
            ids_pub = {}
            exitos = 0

            # Instagram (Usamos el video si existe, si no la imagen)
            try:
                # Aquí podrías decidir si publicas el video o la imagen en IG
                res = self.meta_publisher.publish_to_meta(txt_social, img_url)
                ids_pub["ig"] = res.get("id")
                exitos += 1
            except Exception as e:
                print(f"❌ IG Error: {e}")

            # Facebook e LinkedIn (Igual que antes)
            try:
                self.meta_publisher.publish_to_facebook(txt_social, img_url)
                exitos += 1
            except Exception:
                pass

            if self.linkedin_publisher:
                try:
                    res = self.linkedin_publisher.publish_image_post(
                        txt_linkedin, img_url
                    )
                    ids_pub["li"] = res.get("id")
                    exitos += 1
                except Exception:
                    pass

            if exitos > 0:
                # Actualizamos el Excel con IDs y la URL del video
                ids_pub["url_video"] = video_url_final
                logger.update_after_publish(titulo, "PUBLICADO", ids_pub)
                results.append(titulo)

        return {"status": "completed", "published_count": len(results)}

    def create_and_publish_daily_post(self, topic: str, logger=None) -> Dict[str, Any]:
        research_data = self.search_client.search_site_terms(topic)
        clean_research = "\n".join(research_data.get("items", []))
        metodologia_borgia = "Enfócate en ventas B2B de alto valor."

        raw_data = self.text_generator.generate_borgia_content(
            topic, clean_research, metodologia_borgia
        )
        borgia_content = json.loads(
            raw_data.get("text", "").replace("```json", "").replace("```", "").strip()
        )

        img_result = self.image_generator.generate_social_image(
            borgia_content.get("image_prompt", topic)
        )
        url_final = self.storage_manager.upload_from_url(
            img_result.get("image_url"),
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
        )

        if logger:
            logger.log_post(
                titulo=topic,
                estado="PENDIENTE",
                post_id="N/A",
                objeciones=clean_research,
                fecha=datetime.now().strftime("%Y-%m-%d"),
                resumen_linkedin=borgia_content.get("linkedin_post"),
                resumen_instagram=borgia_content.get("instagram_post"),
                url_imagen=url_final,
            )

        return {
            "status": "generated_and_logged",
            "topic": topic,
            "image_url": url_final,
        }


def build_orchestrator_from_env() -> ContentOrchestrator:
    from backend.app.settings import settings

    client = OpenAIClient()
    return ContentOrchestrator(
        OpenAITextGenerator(client),
        OpenAIImageGenerator(client),
        SearchClient(),
        StorageManager(settings.gcs_bucket_name, settings.gcp_credentials_path),
        MetaSocialPublisher(
            settings.meta_access_token,
            settings.meta_page_id,
            settings.meta_instagram_business_account_id,
        ),
        (
            LinkedInPublisher(
                settings.linkedin_access_token, settings.linkedin_author_urn
            )
            if settings.linkedin_access_token
            else None
        ),
        VideoManager(settings.openai_api_key),  # Pasamos el VideoManager
    )
