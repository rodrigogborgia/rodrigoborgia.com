from __future__ import annotations
import json
import logging
from typing import Any, Dict
import requests


class MetaSocialPublisher:
    """Publica en Facebook e Instagram usando la Meta Graph API."""

    def __init__(
        self,
        page_id: str,
        instagram_business_account_id: str,
        access_token: str,
        graph_version: str = "v17.0",
    ) -> None:
        # Aceptamos inicialización incluso si el token está vacío para evitar crashes en modo dry_run
        self.base_url = f"https://graph.facebook.com/{graph_version}"
        self.page_id = page_id
        self.instagram_business_account_id = instagram_business_account_id
        self.access_token = access_token

    def publish_to_meta(self, caption: str, image_url: str) -> Dict[str, Any]:
        if not self.access_token or "EAAG" not in self.access_token:
            raise ValueError("Token de Meta inválido o no configurado.")

        endpoint = f"{self.base_url}/{self.instagram_business_account_id}/media"
        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.access_token,
        }

        response = requests.post(endpoint, data=payload, timeout=30)
        response.raise_for_status()

        creation_id = response.json().get("id")
        publish_endpoint = (
            f"{self.base_url}/{self.instagram_business_account_id}/media_publish"
        )
        publish_payload = {
            "creation_id": creation_id,
            "access_token": self.access_token,
        }

        publish_response = requests.post(
            publish_endpoint, data=publish_payload, timeout=30
        )
        publish_response.raise_for_status()

        return publish_response.json()


class LinkedInPublisher:
    """Publica posts con imagen en LinkedIn."""

    def __init__(self, access_token: str, author_urn: str) -> None:
        self.access_token = access_token
        self.author_urn = author_urn
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def publish_image_post(self, text: str, image_url: str) -> Dict[str, Any]:
        if not self.access_token:
            raise ValueError("Token de LinkedIn no configurado.")

        endpoint = "https://api.linkedin.com/v2/ugcPosts"
        payload = {
            "author": self.author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [{"status": "READY", "media": image_url}],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        response = requests.post(
            endpoint, headers=self.headers, data=json.dumps(payload), timeout=30
        )
        response.raise_for_status()
        return response.json()
