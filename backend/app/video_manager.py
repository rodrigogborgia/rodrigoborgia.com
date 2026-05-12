import os
import logging
import re
from openai import OpenAI

try:
    from moviepy import AudioFileClip, TextClip, CompositeVideoClip, ColorClip
except ImportError:
    from moviepy.editor import AudioFileClip, TextClip, CompositeVideoClip, ColorClip


class VideoManager:
    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)
        # Ruta estándar para ImageMagick en Mac con Homebrew
        os.environ["IMAGEMAGICK_BINARY"] = "/opt/homebrew/bin/magick"

    def _clean_text_for_display(self, text: str) -> str:
        # Limpiamos etiquetas de guion, voces en off y comillas
        text = re.sub(r"\[.*?\]", "", text)
        text = re.sub(r"(?i)voz\s+en\s+off:?", "", text)
        text = text.replace('"', "")
        return text.strip()

    def create_faceless_video(
        self, text_script: str, image_path: str, output_path: str
    ):
        temp_audio = "temp_voice.mp3"
        try:
            texto_limpio = self._clean_text_for_display(text_script)

            # 1. Generar Audio (TTS)
            logging.info(f"🎙️ Generando voz en off...")
            response = self.client.audio.speech.create(
                model="tts-1", voice="onyx", input=texto_limpio
            )
            response.stream_to_file(temp_audio)
            audio_clip = AudioFileClip(temp_audio)

            # 2. Obtener Transcripción con Timestamps (Whisper)
            logging.info(f"🧠 Sincronizando con Whisper...")
            with open(temp_audio, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-1",
                    response_format="verbose_json",
                    timestamp_granularities=["word"],
                )

            # 3. Preparar Fondo
            bg_clip = ColorClip(size=(1080, 1920), color=(0, 0, 0)).with_duration(
                audio_clip.duration
            )

            # --- Lógica de Fuente Segura para Mac ---
            font_path = "Arial"
            posibles_rutas = [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]

            for ruta in posibles_rutas:
                if os.path.exists(ruta):
                    font_path = ruta
                    break

            logging.info(f"📝 Usando fuente: {font_path}")

            # 4. Generar Clips de Texto con "Zona Segura"
            txt_clips = []
            words = transcript.words
            group_size = 2  # 2 palabras por fragmento para agilidad visual

            for i in range(0, len(words), group_size):
                group = words[i : i + group_size]
                text_chunk = " ".join([w.word for w in group]).upper()
                start_t = group[0].start
                end_t = group[-1].end

                try:
                    txt_snippet = (
                        TextClip(
                            text=text_chunk,
                            font_size=80,  # Tamaño optimizado para evitar cortes
                            color="white",
                            font=font_path,
                            method="caption",
                            # Caja de 850x400 para centrar el texto y evitar que toque el fondo
                            size=(850, 400),
                            text_align="center",
                            vertical_align="center",  # Centrado vertical dentro de la caja
                        )
                        .with_start(start_t)
                        .with_duration(max(0.1, end_t - start_t))
                        .with_position(("center", "center"))
                    )
                    txt_clips.append(txt_snippet)
                except Exception as font_err:
                    logging.warning(
                        f"⚠️ Reintentando clip con fuente default: {font_err}"
                    )
                    txt_snippet = (
                        TextClip(
                            text=text_chunk,
                            font_size=80,
                            color="white",
                            method="caption",
                            size=(850, 400),
                            text_align="center",
                            vertical_align="center",
                        )
                        .with_start(start_t)
                        .with_duration(max(0.1, end_t - start_t))
                        .with_position(("center", "center"))
                    )
                    txt_clips.append(txt_snippet)

            # 5. Render Final
            logging.info(f"🎬 Renderizando video final...")
            final_video = CompositeVideoClip([bg_clip] + txt_clips, size=(1080, 1920))
            final_video = final_video.with_audio(audio_clip)

            final_video.write_videofile(
                output_path, fps=24, codec="libx264", audio_codec="aac", logger=None
            )

            return output_path

        except Exception as e:
            logging.error(f"❌ Error en VideoManager: {e}")
            raise e
        finally:
            if os.path.exists(temp_audio):
                try:
                    audio_clip.close()
                    os.remove(temp_audio)
                except:
                    pass
