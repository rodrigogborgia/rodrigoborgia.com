from __future__ import annotations
import os
import requests
import logging
from pathlib import Path
from typing import Optional
from google.cloud.storage import Client


class StorageManager:
    def __init__(
        self,
        bucket_name: str,
        credentials_path: Optional[str] = None,
        upload_prefix: str = "social-posts",
    ) -> None:
        self.bucket_name = bucket_name
        self.upload_prefix = upload_prefix.strip("/")
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        self.client = self._create_client()

    def _create_client(self) -> Client:
        if self.credentials_path:
            return Client.from_service_account_json(self.credentials_path)
        return Client()

    def upload_from_url(self, url: str, destination_name: str) -> str:
        """Descarga imagen de OpenAI y sube a GCS."""
        print(f"📥 Descargando imagen desde OpenAI...")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        bucket = self.client.bucket(self.bucket_name)
        blob_path = f"{self.upload_prefix}/{destination_name}"
        blob = bucket.blob(blob_path)

        print(f"📤 Subiendo a GCS: {blob_path}...")
        blob.upload_from_string(response.content, content_type="image/png")

        # En buckets con acceso uniforme, no usamos make_public().
        # Construimos la URL directamente.
        return f"https://storage.googleapis.com/{self.bucket_name}/{blob_path}"

    def upload_file(self, local_path: str, destination_path: str) -> str:
        """Sube video u otros archivos a GCS."""
        bucket = self.client.bucket(self.bucket_name)
        full_blob_path = f"{self.upload_prefix}/{destination_path.lstrip('/')}"
        blob = bucket.blob(full_blob_path)

        content_type = "video/mp4" if destination_path.endswith(".mp4") else None

        print(f"📤 Subiendo archivo a GCS: {full_blob_path}...")
        blob.upload_from_filename(local_path, content_type=content_type)

        # URL manual para evitar el error de ACL (BadRequest 400)
        return f"https://storage.googleapis.com/{self.bucket_name}/{full_blob_path}"

    def download_file(self, public_url: str, local_filename: str) -> str:
        """Descarga un archivo de GCS a local."""
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        local_path = temp_dir / local_filename

        try:
            print(f"📥 Descargando para procesar: {public_url}")
            response = requests.get(public_url, stream=True, timeout=30)
            response.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return str(local_path)
        except Exception as e:
            logging.error(f"❌ Error descargando archivo: {e}")
            raise e

    def save_temp_image(self, image_bytes: bytes, filename: str) -> Path:
        temp_dir = Path(os.getenv("TMPDIR", "/tmp")).resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_path = temp_dir / filename
        local_path.write_bytes(image_bytes)
        return local_path

    def upload_image(
        self, local_path: Path, destination_name: Optional[str] = None
    ) -> dict[str, str]:
        bucket = self.client.bucket(self.bucket_name)
        blob_path = f"{self.upload_prefix}/{destination_name or local_path.name}"
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(str(local_path))
        public_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob_path}"
        return {"public_url": public_url, "blob_name": blob_path}
