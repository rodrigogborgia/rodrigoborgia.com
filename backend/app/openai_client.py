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
        REGLAS DE ORO:
        1. ELEGÍ UNO DE LOS 10 PASOS del archivo 'programa_ventas.txt' para basar este post.
        2. Mencioná el paso seleccionado al inicio del post.
        3. CERO EMOJIS.
        4. TONO: Directo, agresivo, estilo Isra Bravo / Chris Voss.
        
        RESPUESTA JSON OBLIGATORIA:
        {{
            "paso_del_metodo": "Nombre o número del paso elegido",
            "linkedin_post": "Tu copy aquí",
            "instagram_post": "Tu copy aquí",
            "image_prompt": "Prompt para DALL-E"
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
        import random

        escenarios = [
            "Dos manos estrechándose con firmeza, enfoque macro en la unión de las manos y texturas de traje premium. Fondo desenfocado y oscuro.",
            "La aleta dorsal de un tiburón estilizado en metal pulido, sobre una superficie de mármol negro. Iluminación lateral dramática.",
            "Una lapicera de lujo de metal oscuro sobre un contrato en papel texturizado, enfoque en la punta de la lapicera. Espacio negativo amplio.",
            "Un maletín de cuero de alta gama cerrado sobre una mesa de madera oscura. Estilo minimalista, cinematográfico.",
        ]
        escenario_elegido = random.choice(escenarios)

        estilo_minimalista = (
            f"Fotografía profesional de altísima gama, 8k, estilo editorial. "
            f"Escenario: {escenario_elegido} "
            "DEBE SER UNA FOTO REALISTA, NO ILUSTRACIÓN, NO DIBUJO. "
            "Profundidad de campo muy baja (bokeh), gran espacio negativo alrededor del objeto principal. "
            "Iluminación dramática tipo estudio, sombras suaves. "
            "Prohibido: Rostros, personas completas, edificios, pantallas, computadoras, desorden, texto, emojis, colores saturados."
        )

        response = self.client.images.generate(
            model="dall-e-3", prompt=estilo_minimalista, n=1, size="1024x1024"
        )
        return {"image_url": response.data[0].url}


class OpenAISettings:
    """Configuraciones para OpenAI."""

    pass
