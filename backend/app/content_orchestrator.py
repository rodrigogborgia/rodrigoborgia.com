from __future__ import annotations
from typing import Any, Dict, Optional, List
import json
import logging
import os
from datetime import datetime

# Importaciones locales
from .storage_manager import StorageManager
from .social_publisher import MetaSocialPublisher, LinkedInPublisher
from .openai_client import OpenAIClient, OpenAITextGenerator, OpenAIImageGenerator
from .search_client import SearchClient
from .video_manager import VideoManager


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
        # Archivos de memoria local
        self.json_path = os.path.join(os.getcwd(), "instrucciones_evolutivas.json")
        self.esencia_path = os.path.join(os.getcwd(), "esencia_borgia.txt")

    def sync_borgia_brain(self, logger):
        """Paso 0: Aprende de las correcciones del Sheet antes de hacer nada."""
        logging.info("🧠 BorgIA sincronizando aprendizaje...")
        if not logger:
            return

        to_process = logger.get_unprocessed_learnings()
        if not to_process:
            logging.info("✅ No hay correcciones nuevas para procesar.")
            return

        for row in to_process:
            tit = row.get("titulo")
            # Extraemos lo generado vs lo corregido por Rodrigo
            li_gen, li_cor = str(row.get("resumen_linkedin", "")), str(
                row.get("linkedin_corregido", "")
            )
            ig_gen, ig_cor = str(row.get("resumen_instagram", "")), str(
                row.get("instagram_corregido", "")
            )

            # Comparación LinkedIn
            if li_cor.strip() and li_gen.strip() != li_cor.strip():
                leccion = self._extraer_regla_gpt(li_gen, li_cor, "LinkedIn")
                self._guardar_leccion(logger, leccion)

            # Comparación Instagram
            if ig_cor.strip() and ig_gen.strip() != ig_cor.strip():
                leccion = self._extraer_regla_gpt(ig_gen, ig_cor, "Instagram")
                self._guardar_leccion(logger, leccion)

            # Marcamos como procesado para no repetir el aprendizaje
            logger.mark_as_learned(tit)
            logging.info(f"✅ Fila '{tit}' procesada por el cerebrito.")

    def _extraer_regla_gpt(self, original: str, corregido: str, canal: str) -> str:
        prompt = (
            f"Actúa como Rodrigo Borgia. Analiza esta corrección técnica de Copy:\n"
            f"Original IA: {original[:400]}...\n"
            f"Tu corrección: {corregido[:400]}...\n"
            "¿Qué patrón específico de escritura cambiaste? (Ej: 'Eliminar adjetivos innecesarios', 'Empezar con una pregunta de dolor', 'No usar emojis en el primer párrafo').\n"
            "PROHIBIDO usar frases genéricas como 'ser persuasivo' o 'ser claro'. Sé brutalmente específico."
        )
        try:
            res = self.text_generator.client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content.strip().replace('"', "")
        except Exception as e:
            logging.error(f"Error extrayendo lección: {e}")
            return ""

    def _guardar_leccion(self, logger, leccion: str) -> bool:
        if not leccion:
            return False

        # 1. Sheet
        success = logger.save_learning_to_sheet(
            {
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "tipo": "Estilo/Copy",
                "ensenanza": leccion,
                "prioridad": "Alta",
            }
        )

        # 2. JSON Local
        if success:
            data = []
            if os.path.exists(self.json_path):
                try:
                    with open(self.json_path, "r") as f:
                        data = json.load(f)
                except:
                    data = []
            data.append(
                {"fecha": datetime.now().strftime("%Y-%m-%d"), "ensenanza": leccion}
            )
            with open(self.json_path, "w") as f:
                json.dump(data[-100:], f, indent=4)
            return True
        return False

    def consolidate_knowledge(self) -> str:
        """Destila los aprendizajes en una 'Esencia' de 10 leyes."""
        logging.info("💎 Consolidando esencia BorgIA...")
        if not os.path.exists(self.json_path):
            return "Sin datos."

        with open(self.json_path, "r") as f:
            try:
                historico = json.load(f)
            except:
                return "Error en JSON"

        if len(historico) < 2:
            return "Pocos datos para consolidar."

        texto_historico = "\n".join([f"- {a['ensenanza']}" for a in historico])

        prompt = f"""
        Sos el curador del estilo de Rodrigo Borgia. 
        Analizá estos micro-aprendizajes de sus correcciones:
        {texto_historico}

        Redactá las '10 Leyes de Estilo de Rodrigo Borgia'. 
        Eliminá redundancias y entregá un manifiesto directo.
        """

        res = self.text_generator.client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        esencia = res.choices[0].message.content.strip()

        with open(self.esencia_path, "w") as f:
            f.write(esencia)

        return esencia

    def create_and_publish_daily_post(self, topic: str, logger=None) -> Dict[str, Any]:
        if logger:
            self.sync_borgia_brain(logger)

        estilo_borgia = ""
        if os.path.exists(self.esencia_path):
            with open(self.esencia_path, "r") as f:
                estilo_borgia = f.read()

        research_data = self.search_client.search_site_terms(topic)
        clean_research = "\n".join(research_data.get("items", []))

        raw_data = self.text_generator.generate_borgia_content(
            topic, clean_research, estilo_borgia
        )
        borgia_content = json.loads(
            raw_data.get("text", "").replace("```json", "").replace("```", "").strip()
        )

        img_result = self.image_generator.generate_social_image(
            borgia_content.get("image_prompt", topic)
        )
        url_final = self.storage_manager.upload_from_url(
            img_result.get("image_url"),
            f"social_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
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
        return {"status": "generated", "topic": topic}

    def run_daily_workflow(self, topic: str, logger=None):
        return self.create_and_publish_daily_post(topic, logger=logger)

    def dispatch_ready_posts(self, logger):
        pendientes = logger.get_pending_publications()
        for post in pendientes:
            if self.linkedin_publisher:
                res = self.linkedin_publisher.publish_text_post(
                    post.get("resumen_linkedin")
                )
                logger.update_after_publish(
                    post.get("titulo"), "PUBLICADO", {"li": res.get("id")}
                )


def build_orchestrator_from_env() -> ContentOrchestrator:
    from .settings import settings

    client = OpenAIClient()
    return ContentOrchestrator(
        text_generator=OpenAITextGenerator(client),
        image_generator=OpenAIImageGenerator(client),
        search_client=SearchClient(),
        storage_manager=StorageManager(
            settings.gcs_bucket_name, settings.gcp_credentials_path
        ),
        meta_publisher=MetaSocialPublisher(
            settings.meta_access_token,
            settings.meta_page_id,
            settings.meta_instagram_business_account_id,
        ),
        linkedin_publisher=(
            LinkedInPublisher(
                settings.linkedin_access_token, settings.linkedin_author_urn
            )
            if settings.linkedin_access_token
            else None
        ),
        video_manager=VideoManager(os.getenv("OPENAI_API_KEY")),
    )
