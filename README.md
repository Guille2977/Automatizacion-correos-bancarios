# Registro automático de movimientos bancarios (Gmail + Python)

Script en Python que lee las notificaciones de un banco en Gmail con **permiso de solo lectura**, extrae los datos de cada movimiento con expresiones regulares, los registra en **SQLite sin duplicados** y genera un **reporte mensual en Excel**.

## Problema

Las notificaciones bancarias llegan por correo, pero no quedan en un registro que permita sumar gastos, comparar meses o separar ingresos de egresos. Hacerlo a mano es lento y propenso a errores.

## Cómo funciona

```
Gmail (solo lectura) → extracción con regex → SQLite (sin duplicados) → reporte en Excel
```

| Módulo | Función |
|---|---|
| `src/gmail_client.py` | Inicia sesión con OAuth 2.0, busca los correos con la sintaxis del buscador de Gmail y obtiene su texto (convierte HTML a texto si hace falta). |
| `src/parser.py` | Extrae monto, moneda, tipo de operación, contraparte y número de operación. Descarta avisos que no son movimientos realizados (compras rechazadas, recordatorios). |
| `src/storage.py` | Guarda los movimientos en SQLite usando el ID del correo como clave primaria. |
| `src/reporte.py` | Genera un Excel con tres hojas: movimientos, resumen mensual (ingresos, egresos y neto) y totales por tipo. |
| `main.py` | Orquesta el proceso y muestra un resumen de la ejecución. |

## Decisiones de diseño

- **Permiso mínimo:** solo `gmail.readonly`. El programa no puede enviar, borrar ni modificar correos.
- **Idempotencia:** se puede ejecutar varias veces sin duplicar movimientos. Además, los correos ya registrados no se vuelven a descargar.
- **Mejor descartar que registrar mal:** si un correo no corresponde a un tipo de operación conocido, o es un aviso de compra rechazada, no se registra.
- **Fecha confiable:** se toma de la cabecera del correo, no del texto.
- **Soles y dólares por separado** en los resúmenes.

## Seguridad y privacidad

- `credentials.json`, `token.json`, `.env` y la carpeta `data/` están en `.gitignore`: las credenciales y los movimientos reales nunca se suben al repositorio.
- Los ejemplos del repositorio (`ejemplos/correos_ficticios.json`) son **ficticios**: banco, comercios, montos y nombres inventados.

## Ejemplo de resultado (datos ficticios)

```
python main.py --demo
Correos encontrados: 7
Correos nuevos procesados: 7
Movimientos guardados: 6
Correos sin monto (no reconocidos): 1
```

Hoja **Resumen mensual** del Excel generado:

| mes | moneda | Ingreso | Egreso | Neto |
|---|---|---|---|---|
| 2026-10 | PEN | 1,295.90 | 245.90 | 1,050.00 |
| 2026-10 | USD | 0.00 | 12.99 | −12.99 |
| 2026-09 | PEN | 0.00 | 300.00 | −300.00 |

Al ejecutarlo de nuevo, `Movimientos guardados: 0`: no se duplica nada.

## Instalación y uso

```bash
git clone https://github.com/Guille2977/Automatizacion-correos-bancarios.git
cd Automatizacion-correos-bancarios
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Probar sin Gmail (datos ficticios):**

```bash
python main.py --demo
python -m pytest -q
```

**Con tu Gmail:**

1. En Google Cloud: crea un proyecto, habilita la **Gmail API**, configura la pantalla de consentimiento (público externo, tu correo como usuario de prueba) y crea un cliente OAuth de tipo **App de escritorio**.
2. Descarga el JSON del cliente como `credentials.json` en la raíz del proyecto.
3. Copia `.env.example` como `.env` y ajusta `GMAIL_QUERY` con el remitente de tu banco.
4. Ejecuta `python main.py`. La primera vez se abrirá el navegador para autorizar el acceso de solo lectura.

## Limitaciones

- Las expresiones regulares están ajustadas al formato de notificaciones de un banco; otro banco puede requerir agregar patrones.
- La contraparte (comercio o beneficiario) no siempre se detecta.
- Solo procesa el texto del correo, no los PDF adjuntos.

## Trabajo futuro

- Leer estados de cuenta en PDF adjuntos.
- Ejecución automática diaria con el Programador de tareas de Windows.
- Clasificar los consumos por categoría (comida, transporte, servicios).

## Tecnologías

Python · Gmail API (OAuth 2.0) · expresiones regulares · SQLite · pandas · openpyxl · pytest

## Autor

Guillermo César Uribe Mejía · [LinkedIn](https://www.linkedin.com/in/guillermo-uribe) · [GitHub](https://github.com/Guille2977)