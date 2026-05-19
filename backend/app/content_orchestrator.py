from __future__ import annotations
from typing import Any, Dict, Optional, List
import json
import logging
import os
from datetime import datetime

# Importaciones locales
from .storage_manager import StorageManager
from .social_publisher import MetaSocialPublisher, LinkedInPublisher, TikTokPublisher
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
        tiktok_publisher: Optional[TikTokPublisher] = None,
    ) -> None:
        self.text_generator = text_generator
        self.image_generator = image_generator
        self.search_client = search_client
        self.storage_manager = storage_manager
        self.meta_publisher = meta_publisher
        self.linkedin_publisher = linkedin_publisher
        self.video_manager = video_manager
        self.tiktok_publisher = tiktok_publisher
        # Archivos de memoria local
        self.json_path = os.path.join(os.getcwd(), "instrucciones_evolutivas.json")
        self.esencia_path = os.path.join(os.getcwd(), "esencia_borgia.txt")

    def sync_borgia_brain(self, logger, max_filas: int = 3):
        """Paso 0: Aprende de las correcciones del Sheet con un límite controlado."""
        logging.info("BorgIA sincronizando aprendizaje...")
        if not logger:
            return

        to_process = logger.get_unprocessed_learnings()
        if not to_process:
            logging.info("No hay correcciones nuevas en el Sheet.")
            return

        # Limitamos el lote para que la API no se congele al generar contenido nuevo
        lote_ejecucion = to_process[:max_filas]
        logging.info(
            f"Procesando un lote controlado de {len(lote_ejecucion)} filas de aprendizaje."
        )

        for row in lote_ejecucion:
            tit = row.get("titulo")
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

            logger.mark_as_learned(tit)
            logging.info(f"Fila '{tit}' marcada como aprendida.")

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
        """Destila los aprendizajes aplicando la combinación de Bravo, Voss y Walker."""
        logging.info("Destilando el Manifiesto Táctico: Bravo + Voss + Walker...")
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
        Eres el Guardián del Estilo de Rodrigo Borgia. 
        Tu misión es fusionar los aprendizajes de Rodrigo con tres mentores específicos:
        1. Isra Bravo: Escritura directa, honesta, que no pide permiso y que vende sin parecer que vende.
        2. Chris Voss: Uso de 'Empatía Táctica' (etiquetado de emociones, preguntas que empiezan con '¿Cómo...?' o '¿Qué...?' para que el otro pense).
        3. Jeff Walker: Disparadores mentales (escasez, anticipación, prueba social).

        Analiza estos aprendizajes de Rodrigo:
        {texto_historico}

        Redacta el 'Manifiesto de Guerra BorgIA'. 
        OBLIGACIONES:
        - El tono debe ser crudo, directo y sin rellenos corporativos ni palabras suaves.
        - Debe incluir el uso de etiquetas de Chris Voss (Ej: 'Parece que te preocupa perder el control de la venta').
        - Debe usar la estructura de anticipación de Walker.
        - PROHIBIDO usar emojis.
        - PROHIBIDO sonar como una IA convencional.

        Entrega 10 leyes de acero que sean órdenes directas de escritura.
        """

        res = self.text_generator.client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        esencia = res.choices[0].message.content.strip()

        # Inyección del cierre exacto solicitado
        remate_fijo = (
            "\n\n--- REMATE OBLIGATORIO ---\n"
            "#ventas #negociacion #MetodoBorgIA #tiburonas #tiburones\n\n"
            "PD: ¿Querés que te avise cuando lance un nuevo entrenamiento táctico? "
            "El único lugar donde aviso primero es en mi lista de distribución. "
            "Entrá en rodrigoborgia.com y no te quedes afuera."
        )

        with open(self.esencia_path, "w") as f:
            f.write(esencia + remate_fijo)

        return esencia

    def create_and_publish_daily_post(self, topic: str, logger=None) -> Dict[str, Any]:
        """Flujo completo de generación inyectando la Esencia Consolidada."""
        if logger:
            self.sync_borgia_brain(logger, max_filas=3)

        estilo_borgia = ""
        if os.path.exists(self.esencia_path):
            with open(self.esencia_path, "r") as f:
                estilo_borgia = f.read()

        research_data = self.search_client.search_site_terms(topic)
        items_research = (
            research_data.get("items", []) if isinstance(research_data, dict) else []
        )
        clean_research = (
            "\n".join(items_research) if items_research else "Sin datos adicionales."
        )

        raw_data = self.text_generator.generate_borgia_content(
            topic, clean_research, metodologia=estilo_borgia
        )
        texto_limpio = (
            raw_data.get("text", "").replace("```json", "").replace("```", "").strip()
        )
        borgia_content = json.loads(texto_limpio)

        img_result = self.image_generator.generate_social_image(
            borgia_content.get("image_prompt", topic)
        )
        url_final = self.storage_manager.upload_from_url(
            img_result.get("value"),
            f"social_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
        )

        if logger:
            logger.log_post(
                titulo=topic,
                estado="PENDIENTE",
                post_id="N/A",
                objeciones=clean_research[:500],
                fecha=datetime.now().strftime("%Y-%m-%d"),
                resumen_linkedin=borgia_content.get("linkedin_post"),
                resumen_instagram=borgia_content.get("instagram_post"),
                url_imagen=url_final,
            )

        logging.info(f"Post creado con éxito para el tópico: {topic}")
        return {"status": "generated", "topic": topic}

    def run_daily_workflow(self, topic: str, logger=None):
        return self.create_and_publish_daily_post(topic, logger=logger)

    def dispatch_ready_posts(self, logger):
        pendientes = logger.get_pending_publications()
        for post in pendientes:
            titulo_post = post.get("titulo")

            # 1. Despacho de Texto/Imagen en LinkedIn
            if self.linkedin_publisher and post.get("resumen_linkedin"):
                res = self.linkedin_publisher.publish_text_post(
                    post.get("resumen_linkedin")
                )
                logger.update_after_publish(
                    titulo_post, "PUBLICADO", {"li": res.get("id")}
                )


def build_orchestrator_from_env() -> ContentOrchestrator:
    from .settings import settings

    client = OpenAIClient()

    from .social_publisher import TikTokPublisher

    tiktok_pub = None
    if os.getenv("TIKTOK_ACCESS_TOKEN"):
        tiktok_pub = TikTokPublisher(
            client_key=os.getenv("TIKTOK_CLIENT_KEY", ""),
            client_secret=os.getenv("TIKTOK_CLIENT_SECRET", ""),
            access_token=os.getenv("TIKTOK_ACCESS_TOKEN", ""),
        )

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
        tiktok_publisher=tiktok_pub,
    )
