from __future__ import annotations
import os
from openai import OpenAI
from typing import Any


class SearchClient:
    """Cliente inteligente que analiza objeciones de ventas usando OpenAI."""

    def __init__(self) -> None:
        # Asegúrate de tener OPENAI_API_KEY en tu .env
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def search_site_terms(
        self, topic: str, site: str = "rodrigoborgia.com", num_results: int = 5
    ) -> dict[str, Any]:
        """
        En lugar de buscar en Google, le pedimos a la IA que genere
        las objeciones más comunes basadas en el tópico proporcionado.
        """
        prompt = f"""
        Actúa como un experto en ventas B2B. Identifica las 5 principales objeciones 
        que un Gerente o Director de Ventas tendría al considerar una solución sobre: '{topic}'.
        Para cada objeción, dame una breve explicación y un ángulo de respuesta.
        Formato: Lista de 5 puntos.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # O el modelo que uses
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )

            content = response.choices[0].message.content
            # Convertimos la respuesta en el formato que espera tu orquestador
            objeciones = content.split("\n")

            return {
                "query": topic,
                "site": "IA_Analysis",
                "items": objeciones,
                "snippets": objeciones,  # Usamos las objeciones como snippets
                "links": [],
                "search_information": {"totalResults": len(objeciones)},
            }

        except Exception as e:
            print(f"[CRITICAL] Error consultando IA: {e}")
            return {
                "query": topic,
                "items": [],
                "snippets": [],
                "links": [],
                "search_information": {},
            }
