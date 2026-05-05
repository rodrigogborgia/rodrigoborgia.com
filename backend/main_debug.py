from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from backend.app.content_orchestrator import build_orchestrator_from_env


def load_local_env() -> None:
    repo_root = Path(__file__).resolve().parent
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Cargando variables de entorno desde {env_path}")
    else:
        print(f"Advertencia: no se encontró {env_path}. Asegurate de tener el archivo .env en backend/")


def main() -> None:
    load_local_env()
    orchestrator = build_orchestrator_from_env()

    topic = "negociación y ventas"
    print("Generando contenido de prueba para topic:", topic)

    text_data = None
    try:
        text_data = orchestrator.text_generator.generate_borgia_content(topic)
        print("Texto generado:\n", text_data.get("text", ""))
    except Exception as e:
        print(f"\n⚠️  Error al generar contenido con Gemini: {type(e).__name__}")
        print(f"   Detalle: {str(e)}")
        if "429" in str(e) or "ResourceExhausted" in str(e):
            print("   → Cuota de API agotada. Intentando con fallback (OpenAI)...")
        else:
            print("   → Continuando con el siguiente paso del proceso...")
        
        # Si hay fallback disponible, intentar usarlo
        if hasattr(orchestrator, 'fallback_text_generator') and orchestrator.fallback_text_generator:
            try:
                print("   → Usando OpenAI como fallback...")
                text_data = orchestrator.fallback_text_generator.generate_borgia_content(topic)
                print("   → Fallback OpenAI devolvió:", text_data)
            except Exception as fallback_error:
                print(f"   ⚠️  Fallback también falló: {fallback_error}")
                raise fallback_error
    
    # Continuar solo si tenemos datos de texto
    if not text_data:
        print("⚠️  No se pudo generar contenido de texto. Continuando con el proceso...")
        return

    image_data = orchestrator.image_generator.generate_social_image(topic)
    image_url = image_data.get("image_url")
    print("URL de imagen generada por Gemini:", image_url)
    if not image_url:
        raise RuntimeError("Gemini no devolvió una URL de imagen válida.")

    import requests

    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    image_bytes = response.content

    filename = "gemini-debug-image.png"
    storage_result = orchestrator.storage_manager.save_and_upload(
        image_bytes,
        filename=filename,
    )

    print("Resultado de almacenamiento en GCS:")
    print(storage_result)


if __name__ == "__main__":
    main()
