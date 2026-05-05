from __future__ import annotations
import gspread
import json
import traceback
import logging  # <--- IMPORTANTE: Agregamos esto
from google.oauth2.service_account import Credentials
from typing import Optional


class SheetLogger:
    def __init__(self, credentials_path: str, sheet_id: str) -> None:
        self.credentials_path = credentials_path
        self.sheet_id = sheet_id
        self._gc: Optional[gspread.client.Client] = None
        self._worksheet: Optional[gspread.Worksheet] = None
        self._connect()

    def _connect(self) -> None:
        try:
            print(f"DEBUG: Intentando leer credenciales en: {self.credentials_path}")
            with open(self.credentials_path, "r") as f:
                creds_data = json.load(f)

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
            ]
            creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
            self._gc = gspread.authorize(creds)
            self._worksheet = self._gc.open_by_key(self.sheet_id).sheet1
        except Exception:
            traceback.print_exc()

    def log_post(
        self,
        titulo,
        red_social,
        post_id,
        objeciones,
        fecha,
        resumen_linkedin,
        resumen_instagram,
        url_imagen,
    ):
        """Registra el post en la hoja de cálculo con columnas separadas."""
        if self._worksheet:
            try:
                self._worksheet.append_row(
                    [
                        fecha,
                        titulo,
                        red_social,
                        post_id,
                        objeciones,
                        resumen_linkedin,
                        resumen_instagram,
                        url_imagen,
                    ]
                )
                logging.info(f"Registro guardado: {titulo}")
            except Exception as e:
                logging.error(f"Error al escribir en el Sheet: {e}")
