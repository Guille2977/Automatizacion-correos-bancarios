"""Resumen diario enviado por correo a tu propia cuenta de Gmail."""

import base64
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

SIMBOLOS = {"PEN": "S/", "USD": "US$"}


def _monto(m: dict) -> str:
    return f"{SIMBOLOS.get(m['moneda'], m['moneda'])} {m['monto']:,.2f}"


def aviso_permiso(archivo: str = "data/autorizado_el.txt", dias_validez: int = 7):
    """Avisa cuando faltan 2 días o menos para que venza el permiso de Google (modo Prueba)."""
    ruta = Path(archivo)
    if not ruta.exists():
        return None
    vence = date.fromisoformat(ruta.read_text(encoding="utf-8").strip()) + timedelta(days=dias_validez)
    dias = (vence - date.today()).days
    if dias > 2:
        return None
    return (f"ATENCIÓN: tu permiso de Google vence el {vence:%d/%m/%Y}. Renuévalo desde tu PC, "
            "en la carpeta del proyecto: del token.json y luego python main.py")


def armar_resumen(nuevos: list, mes: list, url_hoja: str = None, aviso: str = None) -> tuple:
    """Devuelve (asunto, cuerpo). `mes` son los totales del mes actual por sentido y moneda."""
    hoy = date.today().strftime("%d/%m/%Y")
    asunto = f"Resumen de movimientos bancarios – {hoy}: {len(nuevos)} nuevo(s)"
    if aviso:
        asunto += " – renovar permiso"

    lineas = [aviso, ""] if aviso else []
    lineas += [f"Movimientos nuevos desde la última revisión: {len(nuevos)}", ""]
    for m in nuevos[:15]:
        detalle = f" · {m['contraparte']}" if m.get("contraparte") else ""
        lineas.append(f"- {m['fecha'][:16]} · {m['tipo']} · {_monto(m)}{detalle}")
    if len(nuevos) > 15:
        lineas.append(f"... y {len(nuevos) - 15} más.")
    if not nuevos:
        lineas.append("No hubo movimientos nuevos.")

    lineas += ["", "Totales del mes actual:"]
    if mes:
        for fila in mes:
            lineas.append(f"- {fila['sentido']}s: {_monto(fila)}")
    else:
        lineas.append("- Sin movimientos registrados este mes.")

    if url_hoja:
        lineas += ["", f"Hoja completa: {url_hoja}"]
    lineas += ["", "Enviado automáticamente por tu script de registro de movimientos."]
    return asunto, "\n".join(lineas)


def enviar(servicio_gmail, asunto: str, cuerpo: str) -> str:
    """Envía el correo a la misma cuenta que inició sesión (nunca a terceros)."""
    destinatario = servicio_gmail.users().getProfile(userId="me").execute()["emailAddress"]
    mensaje = EmailMessage()
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)
    raw = base64.urlsafe_b64encode(mensaje.as_bytes()).decode()
    servicio_gmail.users().messages().send(userId="me", body={"raw": raw}).execute()
    return destinatario