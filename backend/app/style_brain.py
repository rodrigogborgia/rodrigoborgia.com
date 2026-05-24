import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from openai import OpenAI

BASE_PATH = Path(__file__).resolve().parent
BRAIN_PATH = BASE_PATH / "instrucciones_evolutivas.json"

# Filosofía de estilo BorgIA: síntesis de tres pilares
BORGIA_PHILOSOPHY = """
Filosofía BorgIA — La Trinidad del Estilo:
1. Copywriting de Isra Bravo: Directo, frontal, provocativo, sin pelos en la lengua. Estructura: Problema → Agitación → Solución.
2. Energía Tony Robbins: Rompe patrones, invoca el poder personal, convoca a la transformación.
3. Academia BorgIA: El lector debe entender claramente el valor y el impacto real de transformarse con BorgIA.
"""


def load_brain(path: Path = BRAIN_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_brain(data: Dict[str, Any], path: Path = BRAIN_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _extract_json(text: str) -> str:
    # Try to find a JSON object in text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def merge_aprendizaje_with_diff_learning(
    original_text: str,
    corrected_text: str,
    platform: str = "general",
    openai_client: OpenAI = None,
    row_id: int | None = None,
) -> List[str]:
    """
    Diff Learning: Analyze what changed between original and corrected text.
    Uses OpenAI to extract patterns Rodrigo applied (via BorgIA philosophy).
    Updates aprendizaje_dinamico based on the diff, NOT on the corrected text alone.

    Args:
        original_text: The AI-generated original post
        corrected_text: The user-edited version of the post
        platform: "linkedin" or "instagram" (for context)
        openai_client: OpenAI client (optional, creates new if None)
        row_id: Row ID from Posteador table (optional, for tracking)

    Returns:
        List of 3-5 style lines (aprendizaje_dinamico) updated based on diff analysis
    """
    if openai_client is None:
        openai_client = OpenAI()

    brain = load_brain()
    current = brain.get("aprendizaje_dinamico", [])
    reglas = brain.get("reglas_fijas", {})

    system_instructions = (
        "Eres un experto en análisis de estilo de escritura bajo la Filosofía BorgIA.\n"
        f"{BORGIA_PHILOSOPHY}\n\n"
        "Tu tarea:\n"
        "1. Compara el texto ORIGINAL (generado por IA) con el CORREGIDO (editado por Rodrigo).\n"
        "2. Detecta patrones eliminados, tono añadido, remates o estructuras que Rodrigo aplicó.\n"
        "3. Extrae qué reglas de estilo usó Rodrigo para hacer esos cambios.\n"
        "4. NO toques las `reglas_fijas` (hashtags, PD, palabras clave obligatorias).\n"
        "5. Devuelve SOLO un JSON con la clave `aprendizaje_dinamico` cuyo valor es un arreglo de 3 a 5 líneas cortas y accionables."
    )

    user_prompt = f"""
Aprendizaje dinámico ACTUAL (antes del análisis):
{json.dumps(current, ensure_ascii=False, indent=2)}

Reglas fijas (NO EDITAR):
{json.dumps(reglas, ensure_ascii=False, indent=2)}

--- ANÁLISIS COMPARATIVO (Diff Learning) ---
Plataforma: {platform}

TEXTO ORIGINAL (generado por IA):
"{original_text}"

TEXTO CORREGIDO (editado por Rodrigo):
"{corrected_text}"

---
Pregunta: ¿Qué patrones, muletillas, estructuras o remates ELIMINÓ Rodrigo del original?
¿Qué tono, energía o propósito AÑADIÓ basándose en la Filosofía BorgIA?

Fusiona ese análisis con el aprendizaje_dinamico actual y devuelve el JSON actualizado.
"""

    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=400,
        temperature=0.2,
    )

    content = (
        resp.choices[0].message.content
        if hasattr(resp.choices[0].message, "content")
        else resp.choices[0].message["content"]
    )
    json_text = _extract_json(content)
    try:
        parsed = json.loads(json_text)
        new_aprendizaje = parsed.get("aprendizaje_dinamico")
        if not isinstance(new_aprendizaje, list):
            raise ValueError("aprendizaje_dinamico not a list")
    except Exception:
        # Fallback: use lines from raw content, take up to 5 non-empty lines
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        new_aprendizaje = lines[:5]

    # Sanitize: ensure short lines and limit to 5
    new_aprendizaje = [
        l.replace("\n", " ").strip() for l in new_aprendizaje if l.strip()
    ][:5]

    # Update brain with history
    brain_old = brain.copy()
    brain["aprendizaje_dinamico"] = new_aprendizaje
    brain.setdefault("meta", {})["last_updated"] = datetime.utcnow().isoformat() + "Z"
    history_entry = {
        "ts": brain["meta"]["last_updated"],
        "platform": platform,
        "row_id": row_id,
        "original_sample": (
            (original_text[:300] + "...") if len(original_text) > 300 else original_text
        ),
        "corrected_sample": (
            (corrected_text[:300] + "...")
            if len(corrected_text) > 300
            else corrected_text
        ),
        "previous": brain_old.get("aprendizaje_dinamico", []),
        "new": new_aprendizaje,
    }
    brain.setdefault("meta", {}).setdefault("history", []).append(history_entry)
    save_brain(brain)
    return new_aprendizaje


def build_system_prompt_for_generation(
    topic: str = "", extra_instructions: str = ""
) -> Dict[str, str]:
    """
    Returns a dict with `system_prompt` and `user_prompt` ready to pass to the chat completion.
    It merges reglas_fijas and aprendizaje_dinamico into the system prompt.
    """
    brain = load_brain()
    reglas = brain.get("reglas_fijas", {})
    aprendizaje = brain.get("aprendizaje_dinamico", [])

    system_lines = [
        "Eres BorgIA, un generador de posts que debe seguir reglas fijas y adaptar su estilo al usuario.",
        "Reglas fijas:",
        reglas.get("pd", ""),
        "Hashtags finales:",
        reglas.get("hashtags_block", ""),
        "--",
        "Estilo del usuario (aprendizaje dinámico):",
    ]
    system_lines += aprendizaje
    if extra_instructions:
        system_lines += ["--", extra_instructions]

    system_prompt = "\n".join([l for l in system_lines if l])
    user_prompt = (
        f"Escribe un post sobre: {topic}\nGenera título, 3 párrafos cortos y termina con el bloque de hashtags y el PD."
        if topic
        else "Genera un post siguiendo las instrucciones del sistema."
    )
    return {"system_prompt": system_prompt, "user_prompt": user_prompt}
