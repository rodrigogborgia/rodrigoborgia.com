from __future__ import annotations
import gspread
import json
import traceback
import logging
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

    def get_last_corrections(self, limit: int = 3) -> list[dict]:
        """Recupera las últimas N filas que tienen correcciones."""
        if not self._worksheet:
            return []
        
        # Obtenemos todas las filas
        all_data = self._worksheet.get_all_records()
        
        # Filtramos solo las que tienen algo en las columnas de corrección
        corrections = [
            row for row in all_data 
            if row.get("linkedin_corregido") or row.get("instagram_corregido")
        ]
        
        # Retornamos las últimas 'limit'
        return corrections[-limit:]
    
    def log_post(
        self,
        titulo: str,
        red_social: str,
        post_id: str,
        objeciones: str,
        fecha: str,
        resumen_linkedin: str,
        resumen_instagram: str,
        url_imagen: str,
        linkedin_corregido: str = "",
        instagram_corregido: str = "",
    ):
        """Registra el post en la hoja de cálculo con columnas separadas y espacio para correcciones."""
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
                        linkedin_corregido,
                        instagram_corregido,
                    ]
                )
                logging.info(f"Registro guardado correctamente: {titulo}")
            except Exception as e:
                logging.error(f"Error al escribir en el Sheet: {e}")
