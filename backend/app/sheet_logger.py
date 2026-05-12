from __future__ import annotations
import gspread
import json
import traceback
import logging
from google.oauth2.service_account import Credentials
from typing import Optional, Dict


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

    def log_post(
        self,
        titulo,
        estado,
        post_id,  # Este se guarda pero el flujo lo marca como N/A al inicio
        objeciones,
        fecha,
        resumen_linkedin,
        resumen_instagram,
        url_imagen,
        linkedin_corregido="",
        instagram_corregido="",
    ):
        """
        Registra un nuevo post respetando el orden exacto de tus columnas:
        fecha, titulo, estado, linkedin, instagram, url_imagen, linkedin_corregido, instagram_corregido,
        ig_likes, ig_comments, fb_likes, fb_comments, li_likes, li_comments,
        engagement_total, engagement_rate, horario_ideal, fecha_programada,
        id_instagram, id_facebook, id_linkedin
        """
        if self._worksheet:
            try:
                # Armamos la fila con celdas vacías para las métricas y fecha_programada
                # para que la fila tenga la longitud correcta
                nueva_fila = [
                    fecha,  # A: fecha
                    titulo,  # B: titulo
                    estado,  # C: estado
                    resumen_linkedin,  # D: linkedin
                    resumen_instagram,  # E: instagram
                    url_imagen,  # F: url_imagen
                    linkedin_corregido,  # G: linkedin_corregido
                    instagram_corregido,  # H: instagram_corregido
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",  # I a N: métricas (likes/comments)
                    "",
                    "",
                    "",
                    "",  # O a R: engagement y programación
                    "",
                    "",
                    "",  # S a U: IDs de redes (se llenan al publicar)
                ]

                self._worksheet.append_row(nueva_fila)
                logging.info(f"✅ Registro guardado en Excel: {titulo}")
            except Exception as e:
                logging.error(f"Error al escribir en el Sheet: {e}")

    def get_last_corrections(self, limit: int = 3) -> list[dict]:
        if not self._worksheet:
            return []
        all_data = self._worksheet.get_all_records()
        corrections = [
            row
            for row in all_data
            if row.get("linkedin_corregido") or row.get("instagram_corregido")
        ]
        return corrections[-limit:]

    def get_pending_publications(self) -> list[dict]:
        """Busca filas donde la columna 'estado' sea 'publicar'."""
        if not self._worksheet:
            return []
        all_data = self._worksheet.get_all_records()
        return [row for row in all_data if str(row.get("estado")).lower() == "publicar"]

    def update_after_publish(
        self, titulo: str, nuevo_estado: str, ids_dict: Dict[str, str] = None
    ):
        """
        Busca el post por título y actualiza el estado y los IDs dinámicamente.
        """
        if not self._worksheet:
            return
        try:
            cell = self._worksheet.find(titulo)
            row_idx = cell.row
            headers = self._worksheet.row_values(1)

            # 1. Actualizar 'estado'
            try:
                estado_col = headers.index("estado") + 1
                self._worksheet.update_cell(row_idx, estado_col, nuevo_estado)
            except ValueError:
                self._worksheet.update_cell(row_idx, 3, nuevo_estado)

            # 2. Actualizar los IDs buscando la columna por nombre
            if ids_dict:
                mapping = {
                    "ig": "id_instagram",
                    "fb": "id_facebook",
                    "li": "id_linkedin",
                }
                for key, col_name in mapping.items():
                    if key in ids_dict and ids_dict[key]:
                        try:
                            col_idx = headers.index(col_name) + 1
                            self._worksheet.update_cell(row_idx, col_idx, ids_dict[key])
                        except ValueError:
                            logging.warning(f"No encontré la columna {col_name}")

            logging.info(f"✅ Post '{titulo}' actualizado exitosamente.")
        except Exception as e:
            logging.error(f"Error en update_after_publish: {e}")

    def update_metrics(self, titulo: str, metrics_dict: Dict[str, any]):
        """
        Actualiza todas las columnas de métricas para un post específico.
        """
        if not self._worksheet:
            return
        try:
            cell = self._worksheet.find(titulo)
            row_idx = cell.row
            headers = self._worksheet.row_values(1)

            # Mapeo de campos a columnas del Excel
            mapping = {
                "ig_likes": metrics_dict.get("ig", {}).get("likes", 0),
                "ig_comments": metrics_dict.get("ig", {}).get("comments", 0),
                "fb_likes": metrics_dict.get("fb", {}).get("likes", 0),
                "fb_comments": metrics_dict.get("fb", {}).get("comments", 0),
                "li_likes": metrics_dict.get("li", {}).get("likes", 0),
                "li_comments": metrics_dict.get("li", {}).get("comments", 0),
                "engagement_total": metrics_dict.get("total_engagement", 0),
            }

            for col_name, value in mapping.items():
                try:
                    col_idx = headers.index(col_name) + 1
                    self._worksheet.update_cell(row_idx, col_idx, value)
                except ValueError:
                    continue

            logging.info(f"📊 Métricas actualizadas para: {titulo}")
        except Exception as e:
            logging.error(f"Error actualizando métricas: {e}")
