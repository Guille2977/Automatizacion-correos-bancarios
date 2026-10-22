"""Sincronización de movimientos con una hoja de Google Sheets."""

from pathlib import Path

from googleapiclient.discovery import build

ENCABEZADOS = ["fecha", "tipo", "sentido", "monto", "moneda", "contraparte", "operacion", "asunto", "id_correo"]
PESTANA = "Movimientos"


def conectar(creds):
    return build("sheets", "v4", credentials=creds)


def obtener_hoja(servicio, archivo_id: str = "data/hoja_id.txt", titulo: str = "Movimientos bancarios") -> str:
    """Devuelve el ID de la hoja. La primera vez la crea en tu Drive y guarda su ID."""
    ruta = Path(archivo_id)
    if ruta.exists():
        return ruta.read_text(encoding="utf-8").strip()

    hoja = servicio.spreadsheets().create(
        body={"properties": {"title": titulo}, "sheets": [{"properties": {"title": PESTANA}}]},
        fields="spreadsheetId",
    ).execute()
    hoja_id = hoja["spreadsheetId"]
    servicio.spreadsheets().values().update(
        spreadsheetId=hoja_id, range=f"{PESTANA}!A1",
        valueInputOption="RAW", body={"values": [ENCABEZADOS]},
    ).execute()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(hoja_id, encoding="utf-8")
    return hoja_id


def url(hoja_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{hoja_id}"


def agregar(servicio, hoja_id: str, movimientos: list) -> int:
    """Agrega los movimientos como filas nuevas al final de la hoja."""
    if not movimientos:
        return 0
    filas = [["" if m.get(c) is None else m[c] for c in ENCABEZADOS] for m in movimientos]
    servicio.spreadsheets().values().append(
        spreadsheetId=hoja_id, range=f"{PESTANA}!A1",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": filas},
    ).execute()
    return len(filas)


AZUL = {"red": 0.12, "green": 0.31, "blue": 0.55}
BLANCO = {"red": 1, "green": 1, "blue": 1}
GRIS = {"red": 0.95, "green": 0.96, "blue": 0.98}
VERDE = {"red": 0.10, "green": 0.50, "blue": 0.25}
ROJO = {"red": 0.75, "green": 0.15, "blue": 0.15}
MARGEN = 30          # píxeles extra para el botón de filtro del encabezado
ANCHO_MAXIMO = 700   # para que una columna muy larga no ocupe toda la pantalla


def _regla_texto(gid: int, columna: int, texto: str, color: dict) -> dict:
    return {"addConditionalFormatRule": {"index": 0, "rule": {
        "ranges": [{"sheetId": gid, "startRowIndex": 1, "startColumnIndex": columna, "endColumnIndex": columna + 1}],
        "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": texto}]},
                        "format": {"textFormat": {"foregroundColor": color, "bold": True}}},
    }}}


def dar_formato(servicio, hoja_id: str) -> None:
    """Encabezado con color, fila fija, filtros, montos con 2 decimales y anchos de columna."""
    info = servicio.spreadsheets().get(
        spreadsheetId=hoja_id, fields="sheets(properties(sheetId,title),bandedRanges(bandedRangeId))"
    ).execute()
    pestana = next(s for s in info["sheets"] if s["properties"]["title"] == PESTANA)
    gid = pestana["properties"]["sheetId"]
    n = len(ENCABEZADOS)
    columna = {nombre: i for i, nombre in enumerate(ENCABEZADOS)}

    def columnas(inicio, fin):
        return {"sheetId": gid, "dimension": "COLUMNS", "startIndex": inicio, "endIndex": fin}

    pedidos = [
        {"updateSheetProperties": {"properties": {"sheetId": gid, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {
            "range": {"sheetId": gid, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n},
            "cell": {"userEnteredFormat": {"backgroundColor": AZUL, "horizontalAlignment": "CENTER",
                                           "textFormat": {"bold": True, "foregroundColor": BLANCO}}},
            "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)"}},
        {"repeatCell": {
            "range": {"sheetId": gid, "startRowIndex": 1, "startColumnIndex": columna["monto"],
                      "endColumnIndex": columna["monto"] + 1},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}}},
            "fields": "userEnteredFormat.numberFormat"}},
        {"setBasicFilter": {"filter": {"range": {"sheetId": gid, "startColumnIndex": 0, "endColumnIndex": n}}}},
        # El ID del correo es técnico: se oculta.
        {"updateDimensionProperties": {"range": columnas(columna["id_correo"], columna["id_correo"] + 1),
                                       "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
    ]
    visibles = columnas(0, columna["id_correo"])
    pedidos.append({"autoResizeDimensions": {"dimensions": visibles}})  # ajuste automático al contenido
    if not pestana.get("bandedRanges"):  # filas alternadas y colores por sentido: solo la primera vez
        pedidos += [
            {"addBanding": {"bandedRange": {
                "range": {"sheetId": gid, "startColumnIndex": 0, "endColumnIndex": n},
                "rowProperties": {"headerColor": AZUL, "firstBandColor": BLANCO, "secondBandColor": GRIS}}}},
            _regla_texto(gid, columna["sentido"], "Ingreso", VERDE),
            _regla_texto(gid, columna["sentido"], "Egreso", ROJO),
        ]
    servicio.spreadsheets().batchUpdate(spreadsheetId=hoja_id, body={"requests": pedidos}).execute()

    # El ajuste automático no cuenta el botón de filtro: se suma un margen a cada ancho calculado
    datos = servicio.spreadsheets().get(
        spreadsheetId=hoja_id, ranges=[f"{PESTANA}!A1:{chr(64 + columna['id_correo'])}1"],
        fields="sheets(data(columnMetadata(pixelSize)))",
    ).execute()
    anchos = [c.get("pixelSize", 100) for c in datos["sheets"][0]["data"][0]["columnMetadata"]]
    margenes = [
        {"updateDimensionProperties": {"range": columnas(i, i + 1),
                                       "properties": {"pixelSize": min(ancho + MARGEN, ANCHO_MAXIMO)},
                                       "fields": "pixelSize"}}
        for i, ancho in enumerate(anchos)
    ]
    servicio.spreadsheets().batchUpdate(spreadsheetId=hoja_id, body={"requests": margenes}).execute()