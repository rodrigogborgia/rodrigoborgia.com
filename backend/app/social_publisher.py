from __future__ import annotations
import json
import logging
from typing import Any, Dict
import requests
import time


class MetaSocialPublisher:
    """Publica en Facebook e Instagram usando la Meta Graph API."""

    def __init__(
        self,
        access_token: str,
        page_id: str,
        instagram_business_account_id: str,
        graph_version: str = "v17.0",
    ) -> None:
        self.base_url = f"https://graph.facebook.com/{graph_version}"
        self.access_token = access_token
        self.page_id = page_id
        self.instagram_business_account_id = instagram_business_account_id

    def get_best_publishing_hour(self) -> int:
        """Consulta los insights de Meta para determinar la hora de mayor actividad."""
        if not self.access_token:
            return 9

        endpoint = f"{self.base_url}/{self.instagram_business_account_id}/insights"
        params = {
            "metric": "online_followers",
            "period": "lifetime",
            "access_token": self.access_token,
        }

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json().get("data", [])
            if not data:
                return 9
            values = data[0].get("values", [{}])[0].get("value", {})
            if not values:
                return 9
            best_hour = max(values, key=values.get)
            logging.info(
                f"📊 Meta Insights: La mejor hora detectada es las {best_hour}:00 hs"
            )
            return int(best_hour)
        except Exception as e:
            logging.error(f"Error consultando Insights: {e}")
            return 9

    def publish_to_meta(self, caption: str, image_url: str) -> Dict[str, Any]:
        """Publica específicamente en Instagram."""
        if not self.access_token:
            raise ValueError("Token de Meta inválido o no configurado.")

        endpoint = f"{self.base_url}/{self.instagram_business_account_id}/media"
        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.access_token,
        }

        logging.info(f"📸 Subiendo imagen a Instagram...")
        response = requests.post(endpoint, data=payload, timeout=30)
        response.raise_for_status()
        creation_id = response.json().get("id")

        logging.info(
            f"⏳ Esperando 10s para el procesamiento de Instagram (ID: {creation_id})..."
        )
        time.sleep(10)

        publish_endpoint = (
            f"{self.base_url}/{self.instagram_business_account_id}/media_publish"
        )
        publish_payload = {
            "creation_id": creation_id,
            "access_token": self.access_token,
        }

        logging.info(f"🚀 Publicando definitivamente en Instagram...")
        publish_response = requests.post(
            publish_endpoint, data=publish_payload, timeout=30
        )
        publish_response.raise_for_status()

        return publish_response.json()

    def publish_to_facebook(self, caption: str, image_url: str) -> Dict[str, Any]:
        """Publica en el feed de la página."""
        if not self.access_token:
            raise ValueError("Token de Meta no configurado.")

        endpoint = f"{self.base_url}/{self.page_id}/feed"
        payload = {
            "message": caption,
            "link": image_url,
            "access_token": self.access_token,
        }

        logging.info(f"🔵 Publicando en Facebook Feed...")
        response = requests.post(endpoint, data=payload, timeout=30)

        if response.status_code != 200:
            logging.error(f"❌ Error en Facebook: {response.json()}")
            response.raise_for_status()

        return response.json()

    def get_instagram_metrics(self, media_id: str) -> Dict[str, int]:
        """Obtiene likes y comentarios de un post de Instagram."""
        endpoint = f"{self.base_url}/{media_id}"
        params = {
            "fields": "like_count,comments_count",
            "access_token": self.access_token,
        }
        try:
            res = requests.get(endpoint, params=params, timeout=20)
            res.raise_for_status()
            data = res.json()
            return {
                "likes": data.get("like_count", 0),
                "comments": data.get("comments_count", 0),
            }
        except Exception as e:
            logging.error(f"Error métricas IG ({media_id}): {e}")
            return {"likes": 0, "comments": 0}

    def get_facebook_metrics(self, post_id: str) -> Dict[str, int]:
        """Obtiene likes (reacciones) y comentarios de un post de Facebook."""
        endpoint = f"{self.base_url}/{post_id}"
        params = {
            "fields": "reactions.summary(total_count),comments.summary(total_count)",
            "access_token": self.access_token,
        }
        try:
            res = requests.get(endpoint, params=params, timeout=20)
            res.raise_for_status()
            data = res.json()
            return {
                "likes": data.get("reactions", {})
                .get("summary", {})
                .get("total_count", 0),
                "comments": data.get("comments", {})
                .get("summary", {})
                .get("total_count", 0),
            }
        except Exception as e:
            logging.error(f"Error métricas FB ({post_id}): {e}")
            return {"likes": 0, "comments": 0}


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
        """Versión simplificada y estable para LinkedIn."""
        if not self.access_token:
            raise ValueError("Token de LinkedIn no configurado.")

        endpoint = "https://api.linkedin.com/v2/ugcPosts"

        payload = {
            "author": self.author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "originalUrl": image_url,
                            "title": {"text": "Rodrigo Borgia - Estrategia de Ventas"},
                        }
                    ],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        logging.info(f"🔗 Publicando en LinkedIn (Modo Estable)...")

        response = requests.post(
            endpoint, headers=self.headers, data=json.dumps(payload), timeout=30
        )

        if response.status_code not in [200, 201]:
            logging.error(f"❌ Error final LinkedIn: {response.json()}")
            response.raise_for_status()

        return response.json()

    def get_metrics(self, share_urn: str) -> Dict[str, int]:
        """Obtiene interacciones de LinkedIn probando formatos Share y UGC."""
        # Intentamos primero con el URN tal cual viene (Share o UGC)
        formats_to_try = [share_urn]

        # Si viene como share, preparamos el formato ugcPost por si acaso
        if "share" in share_urn:
            formats_to_try.append(share_urn.replace("share", "ugcPost"))
        elif "ugcPost" in share_urn:
            formats_to_try.append(share_urn.replace("ugcPost", "share"))

        for urn in formats_to_try:
            endpoint = f"https://api.linkedin.com/v2/socialActions/{urn}"
            try:
                res = requests.get(endpoint, headers=self.headers, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "likes": data.get("totalShareStatistics", {}).get(
                            "shareCount", 0
                        ),
                        "comments": data.get("totalShareStatistics", {}).get(
                            "commentCount", 0
                        ),
                    }
                else:
                    logging.warning(
                        f"⚠️ Formato {urn} falló con status {res.status_code}"
                    )
            except Exception as e:
                logging.error(f"Error en intento con {urn}: {e}")

        return {"likes": 0, "comments": 0}
