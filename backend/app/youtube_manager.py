import os
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import pickle


class YouTubeManager:
    def __init__(self, client_secrets_path: str):
        self.client_secrets_path = client_secrets_path
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        self.youtube = self._get_authenticated_service()

    def _get_authenticated_service(self):
        credentials = None
        # El archivo token.pickle guarda tu sesión para no pedir login cada vez
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                credentials = pickle.load(token)

        # Si no hay credenciales válidas, pedimos login
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_path, self.scopes
                )
                # Esto abrirá una ventana en tu navegador la primera vez
                credentials = flow.run_local_server(port=0)

            with open("token.pickle", "wb") as token:
                pickle.dump(credentials, token)

        return build("youtube", "v3", credentials=credentials)

    def upload_short(self, video_path: str, title: str, description: str):
        logging.info(f"🚀 Iniciando subida a YouTube: {title}")

        body = {
            "snippet": {
                "title": title[:100],  # YouTube corta a 100 caracteres
                "description": description,
                "tags": ["shorts", "negocios", "ia", "borgia"],
                "categoryId": "22",  # People & Blogs
            },
            "status": {
                "privacyStatus": "public",  # Puedes poner "private" para probar primero
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        request = self.youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logging.info(f"📤 Subiendo... {int(status.progress() * 100)}%")

        logging.info(f"✅ Video subido con éxito! ID: {response['id']}")
        return response["id"]
