from __future__ import annotations
import os
import datetime
from pathlib import Path
from typing import Optional
from google.cloud.storage import Client

class StorageManager:
    def __init__(self, bucket_name: str, credentials_path: Optional[str] = None, upload_prefix: str = "gemini-images") -> None:
        self.bucket_name = bucket_name
        self.upload_prefix = upload_prefix.strip("/")
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.client = self._create_client()

    def _create_client(self) -> Client:
        if self.credentials_path:
            return Client.from_service_account_json(self.credentials_path)
        return Client()

    def save_temp_image(self, image_bytes: bytes, filename: str) -> Path:
        temp_dir = Path(os.getenv("TMPDIR", "/tmp")).resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_path = temp_dir / filename
        local_path.write_bytes(image_bytes)
        return local_path

    def upload_image(self, local_path: Path, destination_name: Optional[str] = None) -> dict[str, str]:
        bucket = self.client.bucket(self.bucket_name)
        blob = bucket.blob(f"{self.upload_prefix}/{destination_name or local_path.name}")
        blob.upload_from_filename(str(local_path))

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=1),
            method="GET"
        )
        public_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob.name}"

        return {
            "signed_url": signed_url,
            "public_url": public_url,
            "bucket_name": self.bucket_name,
            "blob_name": blob.name,
        }

    def save_and_upload(self, image_bytes: bytes, filename: Optional[str] = None) -> dict[str, str]:
        filename = filename or "gemini_social_image.png"
        if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            filename += ".png"
        local_path = self.save_temp_image(image_bytes, filename)
        upload_result = self.upload_image(local_path, destination_name=local_path.name)
        return {
            "local_path": str(local_path),
            "public_url": upload_result["public_url"],
            "signed_url": upload_result["signed_url"],
            "bucket_name": self.bucket_name,
            "blob_name": upload_result["blob_name"],
        }