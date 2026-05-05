from __future__ import annotations
from typing import Any, Dict
from openai import OpenAI
import os


class OpenAIClient:
    """Cliente base para manejar la conexión con OpenAI."""

    def __init__(self) -> None:
        # Asegúrate de tener OPENAI_API_KEY en tu entorno
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def get_client(self) -> OpenAI:
        return self.client


class OpenAITextGenerator:
    """Generador de contenido utilizando el modelo de OpenAI."""

    def __init__(self, client: OpenAIClient) -> None:
        self.client = client.get_client()

    def generate_borgia_content(
        self, topic: str, research: str, metodologia: str = ""
    ) -> Dict[str, Any]:
        """Genera el contenido basándose en el tema, la investigación y tu metodología."""

        system_instructions = f"""
        Sos el doble digital de Rodrigo Borgia.
        ---
        METODOLOGÍA DE VENTAS B2B (PROGRAMA DE VENTAS B2B):
        {metodologia}
        ---
        Tu tarea es aplicar estrictamente estos pasos y principios en el contenido generado.
        
        IMPORTANTE: Debes responder EXCLUSIVAMENTE con un JSON con la siguiente estructura, sin texto adicional:
        {{
            "linkedin_post": "Texto completo para LinkedIn",
            "instagram_post": "Texto completo para Instagram",
            "image_prompt": "Prompt detallado para DALL-E 3 para crear una imagen representativa"
        }}
        """

        user_content = f"""
        Tema a tratar: {topic}
        Investigación de mercado: {research}
        
        Generá el post ahora.
        """

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )

        return {"text": response.choices[0].message.content}


class OpenAIImageGenerator:
    """Generador de imágenes utilizando DALL-E 3."""

    def __init__(self, client: OpenAIClient) -> None:
        self.client = client.get_client()

    def generate_social_image(self, prompt: str) -> Dict[str, Any]:
        response = self.client.images.generate(
            model="dall-e-3", prompt=prompt, n=1, size="1024x1024"
        )
        return {"image_url": response.data[0].url}


class OpenAISettings:
    """Configuraciones para OpenAI."""

    pass
