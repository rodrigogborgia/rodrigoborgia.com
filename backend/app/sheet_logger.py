from __future__ import annotations
import gspread
import json
import traceback
import logging
from google.oauth2.service_account import Credentials
from typing import Optional, Dict, List


class SheetLogger:
    def __init__(self, credentials_path: str, sheet_id: str) -> None:
        self.credentials_path = credentials_path
        self.sheet_id = sheet_id
        self._gc: Optional[gspread.client.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
        self._worksheet: Optional[gspread.Worksheet] = None
        self._learnings_worksheet: Optional[gspread.Worksheet] = None
        self._connect()

    def _connect(self) -> None:
        """Establece conexión. Si falla, detiene el inicio del sistema."""
        try:
            with open(self.credentials_path, "r") as f:
                creds_data = json.load(f)
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
            ]
            creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
            self._gc = gspread.authorize(creds)
            self._spreadsheet = self._gc.open_by_key(self.sheet_id)
            self._worksheet = self._spreadsheet.sheet1

            # Conexión a la pestaña de aprendizajes
            try:
                self._learnings_worksheet = self._spreadsheet.worksheet(
                    "Aprendizajes_BorgIA"
                )
            except gspread.exceptions.WorksheetNotFound:
                logging.error("❌ No se encontró la pestaña 'Aprendizajes_BorgIA'.")
        except Exception as e:
            logging.critical(f"❌ Error fatal conectando a Google Sheets: {e}")
            raise e

    def get_unprocessed_learnings(self) -> List[Dict]:
        """Trae filas donde aprendizaje != 'SI' y hay correcciones."""
        if not self._worksheet:
            return []
        all_data = self._worksheet.get_all_records()
        # Filtramos: que NO tenga 'SI' y que tenga contenido en las columnas de corregido
        return [
            row
            for row in all_data
            if str(row.get("aprendizaje")).upper() != "SI"
            and (
                str(row.get("linkedin_corregido")).strip() != ""
                or str(row.get("instagram_corregido")).strip() != ""
            )
        ]

    def mark_as_learned(self, titulo: str):
        """Marca como procesado. Lanza error si falla la actualización."""
        if not self._worksheet:
            raise ConnectionError("❌ No hay conexión para marcar aprendizaje.")

        headers = [h.strip() for h in self._worksheet.row_values(1)]
        if "Aprendizaje_Procesado" not in headers:
            col_idx = len(headers) + 1
            self._worksheet.update_cell(1, col_idx, "Aprendizaje_Procesado")
        else:
            col_idx = headers.index("Aprendizaje_Procesado") + 1

        cell = self._worksheet.find(titulo)
        if cell:
            self._worksheet.update_cell(cell.row, col_idx, "SÍ")

    def save_learning_to_sheet(self, data: Dict[str, str]) -> bool:
        """Escribe en la pestaña Aprendizajes_BorgIA."""
        if not self._learnings_worksheet:
            try:
                self._learnings_worksheet = self._spreadsheet.worksheet(
                    "Aprendizajes_BorgIA"
                )
            except:
                logging.error("❌ Pestaña 'Aprendizajes_BorgIA' no encontrada.")
                return False
        try:
            # Columnas: Fecha, Tipo, Enseñanza, Prioridad
            self._learnings_worksheet.append_row(
                [
                    data.get("fecha"),
                    data.get("tipo"),
                    data.get("ensenanza"),
                    data.get("prioridad"),
                ]
            )
            return True
        except Exception as e:
            logging.error(f"❌ Error al escribir aprendizaje: {e}")
            return False

    def log_post(
        self,
        titulo,
        estado,
        post_id,
        objeciones,
        fecha,
        resumen_linkedin,
        resumen_instagram,
        url_imagen,
        linkedin_corregido="",
        instagram_corregido="",
    ):
        """Registra un post. Si falla, detiene el proceso de generación."""
        if not self._worksheet:
            raise ConnectionError("❌ Sin conexión con el Sheet. Abortando registro.")

        nueva_fila = [
            fecha,
            titulo,
            estado,
            resumen_linkedin,
            resumen_instagram,
            url_imagen,
            linkedin_corregido,
            instagram_corregido,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",  # Columna V: Aprendizaje_Procesado
        ]

        try:
            self._worksheet.append_row(nueva_fila)
            logging.info(f"✅ Registro guardado: {titulo}")
        except Exception as e:
            logging.error(f"❌ Error crítico escribiendo fila en Sheets: {e}")
            raise e

    def get_pending_publications(self) -> list[dict]:
        if not self._worksheet:
            return []
        all_data = self._worksheet.get_all_records()
        return [row for row in all_data if str(row.get("estado")).lower() == "publicar"]

    def update_after_publish(
        self, titulo: str, nuevo_estado: str, ids_dict: Dict[str, str] = None
    ):
        """Actualiza estado post-publicación. Si falla, lanza error."""
        if not self._worksheet:
            raise ConnectionError("❌ Sin conexión para actualizar estado final.")

        try:
            cell = self._worksheet.find(titulo)
            row_idx = cell.row
            headers = self._worksheet.row_values(1)

            try:
                estado_col = headers.index("estado") + 1
                self._worksheet.update_cell(row_idx, estado_col, nuevo_estado)
            except ValueError:
                self._worksheet.update_cell(row_idx, 3, nuevo_estado)

            if ids_dict:
                mapping = {
                    "ig": "id_instagram",
                    "fb": "id_facebook",
                    "li": "id_linkedin",
                    "url_video": "url_video",
                }
                for key, col_name in mapping.items():
                    if key in ids_dict and ids_dict[key]:
                        try:
                            col_idx = headers.index(col_name) + 1
                            self._worksheet.update_cell(row_idx, col_idx, ids_dict[key])
                        except ValueError:
                            continue
            logging.info(f"✅ Post '{titulo}' actualizado correctamente.")
        except Exception as e:
            logging.error(f"❌ Fallo en la actualización final del Sheet: {e}")
            raise e
