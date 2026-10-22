"""Registro automático de movimientos bancarios a partir de notificaciones de Gmail.

Uso:
    python main.py          # lee tu Gmail (requiere credentials.json y .env)
    python main.py --demo   # usa los correos ficticios de la carpeta ejemplos/
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src import parser, reporte, storage


def correos_demo(ruta: str = "ejemplos/correos_ficticios.json") -> list:
    """Correos ficticios para probar el programa sin conectarse a Gmail."""
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def correos_gmail(conn, consulta: str, maximo: int) -> tuple:
    from src import gmail_client  # se importa solo si se usa Gmail

    servicio = gmail_client.conectar()
    ids = gmail_client.buscar_ids(servicio, consulta, maximo)
    ya_registrados = storage.ids_registrados(conn)
    pendientes = [i for i in ids if i not in ya_registrados]  # no vuelve a descargar los ya procesados
    return len(ids), [gmail_client.leer_correo(servicio, i) for i in pendientes]


def procesar(correos: list) -> tuple:
    movimientos, no_reconocidos = [], 0
    for correo in correos:
        datos = parser.extraer(correo["asunto"], correo["cuerpo"])
        if datos is None:
            no_reconocidos += 1
            continue
        movimientos.append({
            "id_correo": correo["id"],
            "fecha": correo["fecha"],
            "remitente": correo["remitente"],
            "asunto": correo["asunto"],
            **datos,
        })
    return movimientos, no_reconocidos


def main():
    argumentos = argparse.ArgumentParser(description="Registro de movimientos bancarios desde Gmail")
    argumentos.add_argument("--demo", action="store_true", help="usar los correos ficticios de ejemplos/")
    args = argumentos.parse_args()

    load_dotenv()
    sufijo = "demo" if args.demo else "movimientos"
    conn = storage.conectar(f"data/{sufijo}.db")

    if args.demo:
        correos = correos_demo()
        encontrados = len(correos)
    else:
        consulta = os.getenv("GMAIL_QUERY")
        if not consulta:
            raise SystemExit("Define GMAIL_QUERY en el archivo .env (ver .env.example).")
        encontrados, correos = correos_gmail(conn, consulta, int(os.getenv("MAX_CORREOS", "500")))

    movimientos, no_reconocidos = procesar(correos)
    guardados = storage.guardar(conn, movimientos)
    ruta = reporte.generar(conn, f"data/reporte_{sufijo}.xlsx")

    print(f"Correos encontrados: {encontrados}")
    print(f"Correos nuevos procesados: {len(correos)}")
    print(f"Movimientos guardados: {guardados}")
    print(f"Correos sin monto (no reconocidos): {no_reconocidos}")
    print(f"Reporte: {ruta or 'sin movimientos todavía'}")


if __name__ == "__main__":
    main()