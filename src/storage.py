"""Registro de movimientos en SQLite."""

import sqlite3
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS movimientos (
    id_correo     TEXT PRIMARY KEY,   -- ID del correo en Gmail: evita duplicados
    fecha         TEXT NOT NULL,
    remitente     TEXT,
    asunto        TEXT,
    tipo          TEXT,
    sentido       TEXT,               -- Ingreso o Egreso
    monto         REAL NOT NULL,
    moneda        TEXT,
    contraparte   TEXT,
    operacion     TEXT,
    registrado_en TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

COLUMNAS = ["id_correo", "fecha", "remitente", "asunto", "tipo", "sentido",
            "monto", "moneda", "contraparte", "operacion"]


def conectar(ruta: str) -> sqlite3.Connection:
    if ruta != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta)
    conn.execute(ESQUEMA)
    return conn


def ids_registrados(conn: sqlite3.Connection) -> set:
    return {fila[0] for fila in conn.execute("SELECT id_correo FROM movimientos")}


def guardar(conn: sqlite3.Connection, movimientos: list) -> int:
    """Inserta los movimientos nuevos; los que ya existen se ignoran. Devuelve cuántos se guardaron."""
    antes = conn.total_changes
    conn.executemany(
        f"INSERT OR IGNORE INTO movimientos ({', '.join(COLUMNAS)}) "
        f"VALUES ({', '.join(':' + c for c in COLUMNAS)})",
        movimientos,
    )
    conn.commit()
    return conn.total_changes - antes