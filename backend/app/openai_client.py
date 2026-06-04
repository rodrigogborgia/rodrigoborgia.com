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
        # Usamos gpt-4o para garantizar consistencia absoluta en las instrucciones de estilo
        self.model = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")

    def _load_evolutionary_instructions(self) -> Dict[str, Any]:
        """Carga dinámicamente las reglas y aprendizajes del JSON evolutivo."""
        json_path = os.path.join(
            os.path.dirname(__file__), "instrucciones_evolutivas.json"
        )

        # Valores por defecto de resguardo (en caso de que falle la lectura del JSON)
        default_data = {
            "cierre": "\n\nPD: ¿Querés que te avise cuando lance un nuevo entrenamiento táctico? El único lugar donde aviso primero es en mi lista de distribución. Entrá en rodrigoborgia.com y no te quedes afuera.\n\n#ventas #negociacion #MetodoBorgIA #tiburonas #tiburones",
            "aprendizajes": "Tono: directo, confrontacional y orientado a la acción.\nLongitud: frases cortas y contundentes; párrafos de 1-2 frases.\nVocabulario: metáforas marinas ocasionales; lenguaje de resultado y urgencia.",
        }

        if not os.path.exists(json_path):
            logging.warning(
                f"⚠️ No se encontró {json_path}. Usando configuración por defecto."
            )
            return default_data

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Extraer las reglas fijas y armar el bloque de cierre idéntico al solicitado
            reglas = data.get("reglas_fijas", {})
            pd_text = reglas.get(
                "pd",
                "PD: ¿Querés que te avise cuando lance un nuevo entrenamiento táctico? El único lugar donde aviso primero es en mi lista de distribución. Entrá en rodrigoborgia.com y no te quedes afuera.",
            )
            hashtags = reglas.get(
                "hashtags_block",
                "#ventas #negociacion #MetodoBorgIA #tiburonas #tiburones",
            )
            cierre_consolidado = f"\n\n{pd_text}\n\n{hashtags}"

            # Extraer el aprendizaje dinámico acumulado de la sincronización de las hojas
            lista_aprendizajes = data.get("aprendizaje_dinamico", [])
            aprendizajes_str = (
                "\n".join(lista_aprendizajes)
                if lista_aprendizajes
                else default_data["aprendizajes"]
            )

            return {"cierre": cierre_consolidado, "aprendizajes": aprendizajes_str}
        except Exception as e:
            logging.error(f"❌ Error al leer instrucciones_evolutivas.json: {e}")
            return default_data

    def generate_borgia_content(
        self, topic: str, research: str, metodologia: str = ""
    ) -> Dict[str, Any]:
        logging.info(f"🧠 Generando contenido BorgIA para el tema: {topic}...")

        # Levantamos las reglas del JSON antes de inyectárselas a OpenAI
        instrucciones_json = self._load_evolutionary_instructions()
        cierre_obligatorio = instrucciones_json["cierre"]
        aprendizajes_acumulados = instrucciones_json["aprendizajes"]

        system_instructions = (
            "Sos el Doble Digital de Rodrigo Borgia, estratega experto en ventas corporativas y negociación de alto nivel. "
            "Tu audiencia son vendedores que quieren dejar de mendigar comisiones y convertirse en verdaderos tiburones y tiburonas de la venta.\n\n"
            "⚠️ REGLAS ESTRICTAS DE ESTILO Y FORMATO:\n"
            "1. PROHIBIDO EL USO DE EMOJIS. No uses absolutamente ningún emoji en ningún post. CERO.\n"
            "2. TONO LINKEDIN: Profesional, contundente, directo al hueso, formato B2B, genera autoridad analítica.\n"
            "3. TONO INSTAGRAM: Más relajado, dinámico, enfocado en mentalidad de tiburón, pero manteniendo la seriedad profesional (NUNCA uses lenguaje callejero o marginal).\n\n"
            "📘 FUENTE DE VERDAD ABSOLUTA (Metodología de Ventas):\n"
            f"{metodologia}\n"
            "Si el post menciona algún paso o etapa del proceso de ventas, debes ceñirte ÚNICAMENTE a los nombres y conceptos de los 10 pasos descritos en este documento. Queda totalmente prohibido inventar o usar frameworks de internet.\n\n"
            "🧠 EVOLUCIÓN Y APRENDIZAJE ANTERIOR (Reglas dinámicas extraídas de tus correcciones históricas):\n"
            f"{aprendizajes_acumulados}\n"
            "Aplica rigurosamente estos ajustes de estilo para calcar la escritura real de Rodrigo.\n\n"
            "Formato de salida requerido obligatoriamente en JSON con estas tres llaves:\n"
            "- linkedin_post: El texto completo adaptado para LinkedIn (SIN emojis).\n"
            "- instagram_post: El texto completo adaptado para Instagram (SIN emojis).\n"
            "- image_prompt: Una descripción detallada y profesional para generar la imagen (fotografía B2B corporativa de alta gama).\n"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instructions},
                    {
                        "role": "user",
                        "content": f"Generá los posts para LinkedIn e Instagram sobre el Tema: {topic}. Investigación de contexto/dolor: {research}",
                    },
                ],
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content
            data = json.loads(raw_content)

            # 🛡️ Inyección dura por código: aseguramos el bloque de cierre y hashtags oficiales
            if "linkedin_post" in data:
                clean_post = data["linkedin_post"].split("PD:")[0].strip()
                data["linkedin_post"] = f"{clean_post}{cierre_obligatorio}"

            if "instagram_post" in data:
                clean_post = data["instagram_post"].split("PD:")[0].strip()
                data["instagram_post"] = f"{clean_post}{cierre_obligatorio}"

            return {"text": json.dumps(data)}

        except Exception as e:
            logging.error(f"❌ Error interactuando con OpenAI: {e}")
            raise e


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
