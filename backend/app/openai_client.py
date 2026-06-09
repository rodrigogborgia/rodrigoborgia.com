from __future__ import annotations
from typing import Any, Dict
from openai import OpenAI
import os
import json
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
        self.model = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")

    def generate_borgia_content(
        self,
        topic: str,
        research: str,
        metodologia: str = "",
        aprendizajes_acumulados: str = "",
    ) -> Dict[str, Any]:
        logging.info(
            f"🧠 Generando contenido enfocado en conversión para el tema: {topic}..."
        )

        # Inyectamos el nuevo chip de conversión masiva de leads
        system_instructions = (
            "Sos el doble digital de Rodrigo Borgia, experto en ventas de élite y negociación comercial. "
            f"Tu metodología de ventas central es: {metodologia}. "
            "Tu objetivo de negocio absoluto es hacer crecer la base de inscritos a la lista de distribución de Rodrigo "
            "para su curso premium de Ventas y Negociación Potenciada con IA. "
            "Para lograrlo, usas como gancho un Lead Magnet/PDF gratuito titulado: "
            "'Si dependés de que el cliente no tenga objeciones para cerrar, estás jugando a la lotería con tus comisiones. "
            "Cómo dejar de vender con postura de derrota y activar tu copiloto de IA para multiplicar tus cierres.'\n\n"
            "REGLAS PARA ESCRIBIR EL POST:\n"
            "1. Tono crudo, de trinchera, magnético, que incomode al vendedor tibio y enganche al tiburón.\n"
            "2. Ataca directo dolores como: regalar descuentos por miedo, frustración ante el 'está caro', "
            "vendedores encorvados frente a la pantalla perdiendo comisiones frente a profesionales que sí usan IA.\n"
            "3. Estructura: Frases cortas, contundentes, párrafos de máximo 1 o 2 líneas.\n"
            "4. Cierre obligatorio: Rematar hilando el tema con la invitación a ir a rodrigoborgia.com a descargar el PDF gratuito.\n\n"
            "Respuesta obligatoria estrictamente en formato JSON con llaves exactas: linkedin_post e image_prompt."
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_instructions},
                {
                    "role": "user",
                    "content": f"Tema a desarrollar: {topic}. Investigación/Estructura base: {research}. Aprendizajes previos a respetar: {aprendizajes_acumulados}",
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

            if getattr(image_data, "url", None):
                return {"type": "url", "value": image_data.url}

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
