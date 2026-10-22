# Registro automático de movimientos bancarios (Gmail → Sheets)

Automatización que lee las notificaciones de un banco en Gmail con **permiso de solo lectura**, extrae los datos de cada movimiento con expresiones regulares, los registra **sin duplicados** en SQLite y Google Sheets, y envía un **resumen diario por correo**.

El proyecto tiene dos versiones con la misma lógica:

| Versión | Dónde corre | Uso |
|---|---|---|
| **Python** (`main.py`, `src/`) | En la PC | Versión principal: código modular, pruebas automatizadas, SQLite y reporte en Excel. |
| **Google Apps Script** (`apps-script/`) | En los servidores de Google | Ejecución diaria automática con un activador, aunque la PC esté apagada. |

## Problema

Las notificaciones bancarias llegan por correo, pero no quedan en un registro que permita sumar gastos, comparar meses o separar ingresos de egresos. Hacerlo a mano es lento y propenso a errores.

## Cómo funciona

```
Gmail (solo lectura) → extracción con regex → SQLite / Google Sheets (sin duplicados) → resumen por correo
```

| Módulo | Función |
|---|---|
| `src/gmail_client.py` | Inicia sesión con OAuth 2.0, busca los correos con la sintaxis del buscador de Gmail y obtiene su texto (convierte HTML a texto si hace falta). |
| `src/parser.py` | Extrae monto, moneda, tipo de operación, contraparte y número de operación. Descarta avisos que no son movimientos realizados (compras rechazadas, recordatorios). |
| `src/storage.py` | Guarda los movimientos en SQLite usando el ID del correo como clave primaria, y registra qué ya se copió a Google Sheets. |
| `src/sheets.py` | Crea la hoja de cálculo, agrega las filas nuevas y le da formato (encabezado fijo, filtros, colores por ingreso y egreso). |
| `src/notificador.py` | Arma y envía el resumen diario: movimientos nuevos y totales del mes. |
| `src/reporte.py` | Genera un Excel local con movimientos, resumen mensual y totales por tipo. |
| `apps-script/Codigo.gs` | La misma lógica en JavaScript para ejecutarse en Google Apps Script con un activador diario. |

## Decisiones de diseño

- **Permisos mínimos:** Gmail en solo lectura; en Drive, acceso solo a la hoja que crea el programa (`drive.file`); el resumen se envía únicamente a la cuenta propia.
- **Idempotencia:** se puede ejecutar varias veces sin duplicar movimientos. Los correos ya revisados, incluidos los descartados, no se vuelven a descargar.
- **Sincronización segura:** si falla la conexión al subir a Sheets, esos movimientos se suben en la siguiente ejecución.
- **Mejor descartar que registrar mal:** si un correo no corresponde a un tipo de operación conocido, o es un aviso de compra rechazada, no se registra.
- **La herramienta según la necesidad:** Python para el desarrollo y las pruebas; Apps Script para la ejecución diaria sin depender de la PC ni renovar permisos.

## Seguridad y privacidad

- `credentials.json`, `token.json`, `.env` y la carpeta `data/` están en `.gitignore`: las credenciales y los movimientos reales nunca se suben al repositorio.
- Los ejemplos del repositorio (`ejemplos/correos_ficticios.json`) son **ficticios**: banco, comercios, montos y nombres inventados.

## Ejemplo de resultado (datos ficticios)

```
python main.py --demo
Correos encontrados: 7
Correos nuevos procesados: 7
Movimientos guardados: 6
Correos que no son movimientos (descartados): 1
```

Hoja **Resumen mensual** del Excel generado:

| mes | moneda | Ingreso | Egreso | Neto |
|---|---|---|---|---|
| 2026-10 | PEN | 1,295.90 | 245.90 | 1,050.00 |
| 2026-10 | USD | 0.00 | 12.99 | −12.99 |
| 2026-09 | PEN | 0.00 | 300.00 | −300.00 |

## Uso de la versión Python

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

1. En Google Cloud: crea un proyecto, habilita **Gmail API** y **Google Sheets API**, configura la pantalla de consentimiento (público externo, tu correo como usuario de prueba) y crea un cliente OAuth de tipo **App de escritorio**.
2. Descarga el JSON del cliente como `credentials.json` en la raíz del proyecto.
3. Copia `.env.example` como `.env` y ajusta `GMAIL_QUERY` con el remitente de tu banco.
4. Ejecuta `python main.py`. La primera vez se abrirá el navegador para autorizar los permisos.

| Comando | Qué hace |
|---|---|
| `python main.py` | Registra los movimientos, actualiza SQLite, Excel y Google Sheets, y envía el resumen |
| `python main.py --sin-correo` | Lo mismo, sin enviar el resumen |
| `python main.py --demo` | Usa los correos ficticios, sin conectarse a Google |

## Uso de la versión Apps Script

1. En la hoja de Google Sheets: **Extensiones → Apps Script**.
2. Copia `apps-script/Codigo.gs` y `apps-script/appsscript.json` (activa "Mostrar el archivo de manifiesto" en la configuración del proyecto).
3. Ajusta `CONFIG.CONSULTA` con el remitente de tu banco y ejecuta `registrarMovimientos` una vez para autorizar.
4. En **Activadores**, crea un activador diario para `registrarMovimientos`.

## Limitaciones

- Las expresiones regulares están ajustadas al formato de notificaciones de un banco; otro banco puede requerir agregar patrones.
- La contraparte (comercio o beneficiario) no siempre se detecta.
- Solo procesa el texto del correo, no los PDF adjuntos.
- En la versión Python, mientras la app de Google esté en modo de prueba, el permiso vence cada 7 días; el resumen avisa antes del vencimiento.

## Trabajo futuro

- Leer estados de cuenta en PDF adjuntos.
- Clasificar los consumos por categoría (comida, transporte, servicios).
- Panel con gráficos de gasto mensual en Google Sheets.

## Tecnologías

Python · Gmail API (OAuth 2.0) · Google Sheets API · Google Apps Script · expresiones regulares · SQLite · pandas · openpyxl · pytest

## Autor

Guillermo César Uribe Mejía · [LinkedIn](https://www.linkedin.com/in/guillermo-uribe) · [GitHub](https://github.com/Guille2977)