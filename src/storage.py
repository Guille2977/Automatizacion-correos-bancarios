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
    registrado_en TEXT DEFAULT CURRENT_TIMESTAMP,
    sincronizado  INTEGER DEFAULT 0   -- 1 cuando ya se copió a Google Sheets
);
CREATE TABLE IF NOT EXISTS descartados (
    id_correo TEXT PRIMARY KEY        -- correos revisados que no eran movimientos
);
"""

COLUMNAS = ["id_correo", "fecha", "remitente", "asunto", "tipo", "sentido",
            "monto", "moneda", "contraparte", "operacion"]


def conectar(ruta: str) -> sqlite3.Connection:
    if ruta != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta)
    conn.row_factory = sqlite3.Row
    conn.executescript(ESQUEMA)
    # Bases creadas con la versión anterior: se agrega la columna que falta
    columnas = [fila["name"] for fila in conn.execute("PRAGMA table_info(movimientos)")]
    if "sincronizado" not in columnas:
        conn.execute("ALTER TABLE movimientos ADD COLUMN sincronizado INTEGER DEFAULT 0")
        conn.commit()
    return conn


def ids_registrados(conn: sqlite3.Connection) -> set:
    """IDs ya revisados: movimientos guardados y correos descartados."""
    consulta = "SELECT id_correo FROM movimientos UNION SELECT id_correo FROM descartados"
    return {fila["id_correo"] for fila in conn.execute(consulta)}


def guardar_descartados(conn: sqlite3.Connection, ids: list) -> None:
    conn.executemany("INSERT OR IGNORE INTO descartados (id_correo) VALUES (?)", [(i,) for i in ids])
    conn.commit()


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


def pendientes_de_sincronizar(conn: sqlite3.Connection) -> list:
    """Movimientos que todavía no se copiaron a Google Sheets (incluye los de ejecuciones que fallaron)."""
    filas = conn.execute("SELECT * FROM movimientos WHERE sincronizado = 0 ORDER BY fecha")
    return [dict(fila) for fila in filas]


def marcar_sincronizados(conn: sqlite3.Connection, ids: list) -> None:
    conn.executemany("UPDATE movimientos SET sincronizado = 1 WHERE id_correo = ?", [(i,) for i in ids])
    conn.commit()


def totales_del_mes(conn: sqlite3.Connection, mes: str) -> list:
    """Suma de ingresos y egresos de un mes ('YYYY-MM'), por moneda."""
    filas = conn.execute(
        "SELECT sentido, moneda, ROUND(SUM(monto), 2) AS monto FROM movimientos "
        "WHERE substr(fecha, 1, 7) = ? GROUP BY sentido, moneda ORDER BY sentido DESC, moneda",
        (mes,),
    )
    return [dict(fila) for fila in filas]