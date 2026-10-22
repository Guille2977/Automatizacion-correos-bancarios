"""Reporte en Excel a partir de la base de movimientos."""

import sqlite3
from pathlib import Path

import pandas as pd


def generar(conn: sqlite3.Connection, ruta: str):
    df = pd.read_sql(
        "SELECT fecha, tipo, sentido, monto, moneda, contraparte, operacion, asunto "
        "FROM movimientos ORDER BY fecha DESC",
        conn,
    )
    if df.empty:
        return None

    df["fecha"] = pd.to_datetime(df["fecha"])
    df["mes"] = df["fecha"].dt.strftime("%Y-%m")

    # Ingresos, egresos y saldo neto por mes y moneda
    resumen = df.pivot_table(index=["mes", "moneda"], columns="sentido", values="monto",
                             aggfunc="sum", fill_value=0).reset_index()
    for col in ("Ingreso", "Egreso"):
        if col not in resumen.columns:
            resumen[col] = 0.0
    resumen["Neto"] = resumen["Ingreso"] - resumen["Egreso"]
    resumen = resumen[["mes", "moneda", "Ingreso", "Egreso", "Neto"]].sort_values("mes", ascending=False)
    resumen.columns.name = None

    por_tipo = (df.groupby(["mes", "moneda", "tipo"])
                  .agg(movimientos=("monto", "size"), total=("monto", "sum"))
                  .reset_index()
                  .sort_values(["mes", "total"], ascending=[False, False]))

    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
        df.drop(columns="mes").to_excel(writer, sheet_name="Movimientos", index=False)
        resumen.to_excel(writer, sheet_name="Resumen mensual", index=False)
        por_tipo.to_excel(writer, sheet_name="Por tipo", index=False)

        # Ancho de columnas según el contenido
        for hoja in writer.book.worksheets:
            for columna in hoja.columns:
                ancho = max(len(str(celda.value or "")) for celda in columna)
                hoja.column_dimensions[columna[0].column_letter].width = min(ancho + 2, 60)
    return ruta