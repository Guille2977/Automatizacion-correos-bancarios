"""Extracción de movimientos a partir del texto de una notificación bancaria."""

import re

# Monto con su moneda: "S/ 45.90", "S/. 1,250.00", "US$ 12.99", "PEN 30.00"
PATRON_MONTO = re.compile(r"(S/\.?|US\$|USD|PEN|\$)\s*(\d[\d.,]*\d|\d)")

MONEDAS = {"S/": "PEN", "S/.": "PEN", "PEN": "PEN", "US$": "USD", "USD": "USD", "$": "USD"}

# Tipos en orden de prioridad: el primero que coincide gana.
# "Devolución" va antes que "Consumo" ("devolución de consumo") y
# "Depósito" antes que "Transferencia enviada" ("transferencia recibida").
TIPOS = [
    ("Devolución", r"devoluci[oó]n|extorno"),
    ("Retiro", r"retiro|disposici[oó]n de efectivo"),
    ("Depósito", r"dep[oó]sito|abono|recibiste|te yapearon|transferencia recibida"),
    ("Transferencia enviada", r"transferencia|yapeaste|enviaste"),
    ("Consumo", r"consumo|compra|cargo|pagaste|pago con tu tarjeta"),
]

INGRESOS = {"Devolución", "Depósito"}

# Contraparte con etiqueta: "Comercio: X", "Beneficiario: X"...
PATRON_ETIQUETA = re.compile(
    r"(?:comercio|establecimiento|empresa|beneficiario|destinatario|ordenante|origen)\s*:\s*([^\n.]+)",
    re.IGNORECASE,
)
# Contraparte en mayúsculas después de "en", "de" o "a": "en SUPERMERCADO CENTRAL"
PATRON_MAYUSCULAS = re.compile(r"\b(?:[Ee]n|[Dd]e|a)\s+([A-Z][A-Z0-9&'*-]{2,}\b(?:\s+[A-Z0-9&'*-]+\b)*)")

PATRON_OPERACION = re.compile(
    r"(?:n[uú]mero de operaci[oó]n|nro\.? de operaci[oó]n|c[oó]digo de operaci[oó]n)\s*:?\s*(\d{4,})",
    re.IGNORECASE,
)


def a_numero(texto: str) -> float:
    """Convierte '1,250.00', '1.250,00' o '45,90' en número."""
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):  # formato 1.250,00
            texto = texto.replace(".", "").replace(",", ".")
        else:  # formato 1,250.00
            texto = texto.replace(",", "")
    elif "," in texto:
        decimales = texto.rsplit(",", 1)[1]
        if texto.count(",") == 1 and len(decimales) == 2:  # 45,90
            texto = texto.replace(",", ".")
        else:  # 1,250
            texto = texto.replace(",", "")
    return float(texto)


def detectar_tipo(asunto: str, cuerpo: str) -> str:
    """Busca primero en el asunto (más confiable) y luego en el cuerpo."""
    for texto in (asunto, cuerpo):
        for tipo, patron in TIPOS:
            if re.search(patron, texto, re.IGNORECASE):
                return tipo
    return "Otro"


def detectar_contraparte(cuerpo: str):
    encontrado = PATRON_ETIQUETA.search(cuerpo) or PATRON_MAYUSCULAS.search(cuerpo)
    if not encontrado:
        return None
    return encontrado.group(1).strip(" .,;")[:60]


def extraer(asunto: str, cuerpo: str):
    """Devuelve los datos del movimiento, o None si el correo no tiene un monto."""
    monto = PATRON_MONTO.search(cuerpo) or PATRON_MONTO.search(asunto)
    if not monto:
        return None

    tipo = detectar_tipo(asunto, cuerpo)
    operacion = PATRON_OPERACION.search(cuerpo)
    return {
        "tipo": tipo,
        "sentido": "Ingreso" if tipo in INGRESOS else "Egreso",
        "monto": a_numero(monto.group(2)),
        "moneda": MONEDAS[monto.group(1)],
        "contraparte": detectar_contraparte(cuerpo),
        "operacion": operacion.group(1) if operacion else None,
    }