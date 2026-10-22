"""Registro automático de movimientos bancarios a partir de notificaciones de Gmail.

Uso:
    python main.py                # lee Gmail, actualiza SQLite, Excel y Google Sheets, y envía el resumen
    python main.py --sin-correo   # igual, pero sin enviar el resumen por correo
    python main.py --programado   # para la tarea diaria: si el permiso venció, avisa en vez de abrir el navegador
    python main.py --demo         # usa los correos ficticios de ejemplos/ (sin conectarse a Google)
"""

import argparse
import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from src import parser, reporte, storage


def correos_demo(ruta: str = "ejemplos/correos_ficticios.json") -> list:
    """Correos ficticios para probar el programa sin conectarse a Gmail."""
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def correos_gmail(gmail, conn, consulta: str, maximo: int) -> tuple:
    from src import gmail_client

    ids = gmail_client.buscar_ids(gmail, consulta, maximo)
    ya_registrados = storage.ids_registrados(conn)
    pendientes = [i for i in ids if i not in ya_registrados]  # no vuelve a descargar los ya procesados
    return len(ids), [gmail_client.leer_correo(gmail, i) for i in pendientes]


def procesar(correos: list) -> tuple:
    movimientos, descartados = [], []
    for correo in correos:
        datos = parser.extraer(correo["asunto"], correo["cuerpo"])
        if datos is None:
            descartados.append(correo["id"])
            continue
        movimientos.append({
            "id_correo": correo["id"],
            "fecha": correo["fecha"],
            "remitente": correo["remitente"],
            "asunto": correo["asunto"],
            **datos,
        })
    return movimientos, descartados


def main():
    argumentos = argparse.ArgumentParser(description="Registro de movimientos bancarios desde Gmail")
    argumentos.add_argument("--demo", action="store_true", help="usar los correos ficticios de ejemplos/")
    argumentos.add_argument("--sin-correo", action="store_true", help="no enviar el resumen por correo")
    argumentos.add_argument("--programado", action="store_true",
                            help="ejecución automática: nunca abre el navegador para autorizar")
    args = argumentos.parse_args()

    load_dotenv()
    sufijo = "demo" if args.demo else "movimientos"
    conn = storage.conectar(f"data/{sufijo}.db")

    if args.demo:
        correos = correos_demo()
        encontrados = len(correos)
    else:
        from src import gmail_client, notificador, sheets

        consulta = os.getenv("GMAIL_QUERY")
        if not consulta:
            raise SystemExit("Define GMAIL_QUERY en el archivo .env (ver .env.example).")
        creds = gmail_client.obtener_credenciales(interactivo=not args.programado)
        gmail = gmail_client.conectar(creds)
        encontrados, correos = correos_gmail(gmail, conn, consulta, int(os.getenv("MAX_CORREOS", "500")))

    movimientos, descartados = procesar(correos)
    guardados = storage.guardar(conn, movimientos)
    storage.guardar_descartados(conn, descartados)  # no se vuelven a descargar
    ruta = reporte.generar(conn, f"data/reporte_{sufijo}.xlsx")

    print(f"Correos encontrados: {encontrados}")
    print(f"Correos nuevos procesados: {len(correos)}")
    print(f"Movimientos guardados: {guardados}")
    print(f"Correos que no son movimientos (descartados): {len(descartados)}")
    print(f"Reporte: {ruta or 'sin movimientos todavía'}")

    if args.demo:
        return

    # Google Sheets: se copian los movimientos que aún no están en la hoja
    hojas = sheets.conectar(creds)
    hoja_id = sheets.obtener_hoja(hojas)
    pendientes = storage.pendientes_de_sincronizar(conn)
    sheets.agregar(hojas, hoja_id, pendientes)
    sheets.dar_formato(hojas, hoja_id)
    storage.marcar_sincronizados(conn, [m["id_correo"] for m in pendientes])
    print(f"Filas agregadas a Google Sheets: {len(pendientes)} ({sheets.url(hoja_id)})")

    # Resumen diario por correo
    if not args.sin_correo:
        mes = storage.totales_del_mes(conn, date.today().strftime("%Y-%m"))
        asunto, cuerpo = notificador.armar_resumen(pendientes, mes, sheets.url(hoja_id),notificador.aviso_permiso())
        destinatario = notificador.enviar(gmail, asunto, cuerpo)
        print(f"Resumen enviado a: {destinatario}")


if __name__ == "__main__":
    main()