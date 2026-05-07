from __future__ import annotations
from typing import Any, Dict, Optional
import json
import logging
import os

from backend.app.storage_manager import StorageManager
from backend.app.social_publisher import MetaSocialPublisher, LinkedInPublisher
from backend.app.openai_client import (
    OpenAIClient,
    OpenAITextGenerator,
    OpenAIImageGenerator,
)
from backend.app.search_client import SearchClient


class ContentOrchestrator:
    def __init__(
        self,
        text_generator: OpenAITextGenerator,
        image_generator: OpenAIImageGenerator,
        search_client: SearchClient,
        storage_manager: StorageManager,
        meta_publisher: Optional[MetaSocialPublisher] = None,
        linkedin_publisher: Optional[LinkedInPublisher] = None,
    ) -> None:
        self.text_generator = text_generator
        self.image_generator = image_generator
        self.search_client = search_client
        self.storage_manager = storage_manager
        self.meta_publisher = meta_publisher
        self.linkedin_publisher = linkedin_publisher

    def create_and_publish_daily_post(
        self, topic: str, publish: bool = False
    ) -> Dict[str, Any]:
        # 1. Investigación
        research_data = self.search_client.search_site_terms(topic)
        clean_research = "\n".join(research_data.get("items", []))

        # 2. Carga de metodología y CORRECCIONES HUMANAS (Aprendizaje)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        metodologia_path = os.path.join(base_dir, "programa_ventas.txt")

        metodologia_borgia = "Enfócate en ventas B2B de alto valor."
        if os.path.exists(metodologia_path):
            with open(metodologia_path, "r", encoding="utf-8") as f:
                metodologia_borgia = f.read()

        # Leemos correcciones desde el Sheet
        from backend.app.sheet_logger import SheetLogger
        from backend.app.settings import settings

        logger = SheetLogger(settings.sheet_credentials_path, settings.sheet_id)
        last_corrections = logger.get_last_corrections(limit=3)

        contexto_estilo = (
            "\n\nEJEMPLOS DE MI ESTILO REAL (USAR ESTA CADENCIA Y VOSEO ROSARINO):\n"
        )
        for row in last_corrections:
            if row.get("linkedin_corregido"):
                contexto_estilo += f"- Ejemplo de estilo: {row['linkedin_corregido']}\n"

        metodologia_final = metodologia_borgia + contexto_estilo

        # 3. Generación de texto
        raw_data = self.text_generator.generate_borgia_content(
            topic, clean_research, metodologia_final
        )

        raw_text = (
            raw_data.get("text", "").replace("```json", "").replace("```", "").strip()
        )
        borgia_content = json.loads(raw_text)

        # 4. Generación de Imagen
        image_prompt = borgia_content.get("image_prompt", topic)
        img_result = self.image_generator.generate_social_image(image_prompt)
        image_url = img_result.get("image_url")

        return {"borgia_content": borgia_content, "image_url": image_url}


def build_orchestrator_from_env() -> ContentOrchestrator:
    from backend.app.settings import settings

    openai_client = OpenAIClient()

    return ContentOrchestrator(
        text_generator=OpenAITextGenerator(openai_client),
        image_generator=OpenAIImageGenerator(openai_client),
        search_client=SearchClient(),
        storage_manager=StorageManager(
            settings.gcs_bucket_name, settings.gcp_credentials_path
        ),
    )
