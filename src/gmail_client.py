"""Conexión a Gmail con permiso de solo lectura."""

import base64
import html
import re
from email.utils import parsedate_to_datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Solo lectura: el programa no puede enviar, borrar ni modificar correos.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def conectar(credenciales: str = "credentials.json", token: str = "token.json"):
    """Inicia sesión con OAuth. La primera vez abre el navegador; luego reutiliza token.json."""
    creds = None
    if Path(token).exists():
        creds = Credentials.from_authorized_user_file(token, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flujo = InstalledAppFlow.from_client_secrets_file(credenciales, SCOPES)
            creds = flujo.run_local_server(port=0)
        Path(token).write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def buscar_ids(servicio, consulta: str, maximo: int = 500) -> list:
    """Devuelve los IDs de los correos que cumplen la consulta (misma sintaxis que el buscador de Gmail)."""
    ids, pagina = [], None
    while len(ids) < maximo:
        respuesta = servicio.users().messages().list(
            userId="me", q=consulta, pageToken=pagina, maxResults=min(100, maximo - len(ids))
        ).execute()
        ids += [m["id"] for m in respuesta.get("messages", [])]
        pagina = respuesta.get("nextPageToken")
        if not pagina:
            break
    return ids


def _decodificar(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _partes(parte: dict, tipo: str) -> list:
    """Recorre el correo (que puede tener partes anidadas) y junta las del tipo pedido."""
    if parte.get("mimeType") == tipo and parte.get("body", {}).get("data"):
        return [_decodificar(parte["body"]["data"])]
    encontradas = []
    for subparte in parte.get("parts", []) or []:
        encontradas += _partes(subparte, tipo)
    return encontradas


def html_a_texto(contenido: str) -> str:
    contenido = re.sub(r"<(script|style).*?</\1>", " ", contenido, flags=re.DOTALL | re.IGNORECASE)
    contenido = re.sub(r"<br\s*/?>|</p>|</tr>|</div>", "\n", contenido, flags=re.IGNORECASE)
    contenido = re.sub(r"<[^>]+>", " ", contenido)
    contenido = html.unescape(contenido)
    return re.sub(r"[ \t\xa0]+", " ", contenido).strip()


def extraer_cuerpo(payload: dict) -> str:
    """Prefiere el texto plano; si el correo solo trae HTML, lo convierte a texto."""
    textos = _partes(payload, "text/plain")
    if textos:
        return "\n".join(textos)
    return html_a_texto("\n".join(_partes(payload, "text/html")))


def leer_correo(servicio, id_correo: str) -> dict:
    mensaje = servicio.users().messages().get(userId="me", id=id_correo, format="full").execute()
    cabeceras = {c["name"].lower(): c["value"] for c in mensaje["payload"].get("headers", [])}
    fecha = parsedate_to_datetime(cabeceras["date"]).astimezone() if "date" in cabeceras else None
    return {
        "id": id_correo,
        "fecha": fecha.strftime("%Y-%m-%d %H:%M:%S") if fecha else None,
        "remitente": cabeceras.get("from", ""),
        "asunto": cabeceras.get("subject", ""),
        "cuerpo": extraer_cuerpo(mensaje["payload"]),
    }