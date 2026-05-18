from __future__ import annotations
from typing import Any, Dict
from openai import OpenAI
import os
import logging
import tempfile
import base64


class OpenAIClient:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("❌ No se encontró OPENAI_API_KEY.")
        self.client = OpenAI(api_key=api_key)

    def get_client(self) -> OpenAI:
        return self.client


class OpenAITextGenerator:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client.get_client()
        self.model = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")

    def generate_borgia_content(
        self, topic: str, research: str, metodologia: str = ""
    ) -> Dict[str, Any]:
        system_instructions = (
            f"Sos el doble digital de Rodrigo Borgia. "
            f"Metodología de ventas: {metodologia}. "
            "Respuesta obligatoria en formato JSON con llaves: linkedin_post e image_prompt."
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_instructions},
                {
                    "role": "user",
                    "content": f"Tema: {topic}. Investigación: {research}",
                },
            ],
            response_format={"type": "json_object"},
        )
        return {"text": response.choices[0].message.content}


class OpenAIImageGenerator:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client.get_client()
        self.model = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")

    def generate_social_image(self, prompt: str) -> Dict[str, Any]:
        logging.info(f"🎨 Generando imagen con {self.model}...")

        try:
            response = self.client.images.generate(
                model=self.model,
                prompt=f"Professional B2B photo, realistic, high-end. Scene: {prompt}",
                size="1024x1024",
            )

            image_data = response.data[0]

            # Caso DALL-E
            if getattr(image_data, "url", None):
                return {"type": "url", "value": image_data.url}

            # Caso GPT Image
            if getattr(image_data, "b64_json", None):
                image_bytes = base64.b64decode(image_data.b64_json)

                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")

                temp_file.write(image_bytes)
                temp_file.close()

                return {"type": "file", "value": temp_file.name}

            raise ValueError("La respuesta no contiene url ni b64_json")

        except Exception as e:
            logging.error(f"❌ Error Imagen: {e}")
            raise
