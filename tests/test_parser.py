import json
from pathlib import Path

from src import parser

EJEMPLOS = {c["id"]: c for c in json.loads(
    (Path(__file__).parent.parent / "ejemplos" / "correos_ficticios.json").read_text(encoding="utf-8"))}


def extraer(id_correo):
    correo = EJEMPLOS[id_correo]
    return parser.extraer(correo["asunto"], correo["cuerpo"])


def test_convierte_formatos_de_monto():
    assert parser.a_numero("1,250.00") == 1250.0
    assert parser.a_numero("1.250,00") == 1250.0
    assert parser.a_numero("45,90") == 45.9
    assert parser.a_numero("45.90") == 45.9


def test_consumo_en_soles():
    datos = extraer("demo-01")
    assert datos["tipo"] == "Consumo"
    assert datos["sentido"] == "Egreso"
    assert datos["monto"] == 45.90
    assert datos["moneda"] == "PEN"
    assert datos["contraparte"] == "SUPERMERCADO CENTRAL SAN ISIDRO"
    assert datos["operacion"] == "482910"


def test_compra_en_dolares():
    datos = extraer("demo-02")
    assert datos["moneda"] == "USD"
    assert datos["monto"] == 12.99


def test_deposito_con_miles():
    datos = extraer("demo-03")
    assert datos["tipo"] == "Depósito"
    assert datos["sentido"] == "Ingreso"
    assert datos["monto"] == 1250.0
    assert datos["contraparte"] == "EMPRESA DEMO SAC"


def test_devolucion_tiene_prioridad_sobre_consumo():
    datos = extraer("demo-06")
    assert datos["tipo"] == "Devolución"
    assert datos["sentido"] == "Ingreso"


def test_correo_sin_monto_se_descarta():
    assert extraer("demo-07") is None


def test_compra_rechazada_no_es_movimiento():
    assert parser.extraer("Se rechazó tu compra por fondos insuficientes",
                          "Lo sentimos, tu compra de S/ 30.00 fue rechazada.") is None


def test_pago_de_servicio():
    datos = parser.extraer("CONSTANCIA DE PAGO DE SERVICIO", "Pagaste S/ 89.90 por tu recibo de luz.")
    assert datos["tipo"] == "Pago de servicio"
    assert datos["sentido"] == "Egreso"