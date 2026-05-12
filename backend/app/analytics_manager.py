import requests
import logging


class AnalyticsManager:
    def __init__(self, meta_token: str, linkedin_token: str):
        self.meta_token = meta_token
        self.linkedin_token = linkedin_token

    def get_instagram_metrics(self, media_id: str):
        """Trae likes y comentarios de un post de Instagram."""
        try:
            url = f"https://graph.facebook.com/v19.0/{media_id}"
            params = {
                "fields": "like_count,comments_count",
                "access_token": self.meta_token,
            }
            res = requests.get(url, params=params).json()
            return {
                "likes": res.get("like_count", 0),
                "comments": res.get("comments_count", 0),
            }
        except Exception as e:
            logging.error(f"Error en IG Metrics: {e}")
            return {"likes": 0, "comments": 0}

    def get_facebook_metrics(self, post_id: str):
        """Trae reacciones y comentarios de un post de Facebook."""
        try:
            url = f"https://graph.facebook.com/v19.0/{post_id}"
            params = {
                "fields": "reactions.summary(true),comments.summary(true)",
                "access_token": self.meta_token,
            }
            res = requests.get(url, params=params).json()
            return {
                "likes": res.get("reactions", {})
                .get("summary", {})
                .get("total_count", 0),
                "comments": res.get("comments", {})
                .get("summary", {})
                .get("total_count", 0),
            }
        except Exception as e:
            logging.error(f"Error en FB Metrics: {e}")
            return {"likes": 0, "comments": 0}

    def get_linkedin_metrics(self, post_urn: str):
        """Trae analíticas de LinkedIn."""
        # Nota: La API de LinkedIn requiere configuraciones específicas de permisos
        # Por ahora lo dejamos preparado para el URN
        try:
            url = f"https://api.linkedin.com/v2/socialActions/{post_urn}"
            headers = {"Authorization": f"Bearer {self.linkedin_token}"}
            res = requests.get(url, headers=headers).json()

            likes = res.get("likesSummary", {}).get("aggregatedTotal", 0)
            comments = res.get("commentsSummary", {}).get("aggregatedTotal", 0)
            return {"likes": likes, "comments": comments}
        except Exception as e:
            logging.error(f"Error en LI Metrics: {e}")
            return {"likes": 0, "comments": 0}
