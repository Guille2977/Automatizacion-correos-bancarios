/**
 * Registro automático de movimientos bancarios — versión en la nube (Google Apps Script).
 *
 * Misma lógica que la versión en Python: lee las notificaciones del banco en Gmail (solo lectura),
 * agrega a esta hoja los movimientos nuevos y te envía un resumen por correo.
 * Se ejecuta en los servidores de Google con un activador diario: no necesita la PC encendida.
 */

const CONFIG = {
  CONSULTA: 'from:(notificaciones.bcp.com.pe OR notificacionesbcp.com.pe) newer_than:60d',
  PESTANA: 'Movimientos',
  HORA_DEL_RESUMEN: 20,  // 20 = entre 8 y 9 p. m. (Google elige el minuto dentro de esa hora)
};

const ENCABEZADOS = ['fecha', 'tipo', 'sentido', 'monto', 'moneda', 'contraparte', 'operacion', 'asunto', 'id_correo'];
const COL = Object.fromEntries(ENCABEZADOS.map((nombre, i) => [nombre, i]));

// ---------- Extracción (equivale a src/parser.py) ----------

const PATRON_MONTO = /(S\/\.?|US\$|USD|PEN|\$)\s*(\d[\d.,]*\d|\d)/;
const MONEDAS = { 'S/': 'PEN', 'S/.': 'PEN', 'PEN': 'PEN', 'US$': 'USD', 'USD': 'USD', '$': 'USD' };
const TIPOS = [
  ['Devolución', /devoluci[oó]n|extorno/i],
  ['Retiro', /retiro|disposici[oó]n de efectivo/i],
  ['Depósito', /dep[oó]sito|abono|recibiste|te yapearon|transferencia recibida/i],
  ['Transferencia enviada', /transferencia|yapeaste|enviaste/i],
  ['Pago de servicio', /pago de servicio|pago de recibo/i],
  ['Consumo', /consumo|compra|cargo|pagaste|pago con tu tarjeta/i],
];
const NO_MOVIMIENTO = /rechaz|no se pudo|fondos insuficientes|pronto|recordatorio|programad/i;
const INGRESOS = ['Devolución', 'Depósito'];
const PATRON_ETIQUETA = /(?:comercio|establecimiento|empresa|beneficiario|destinatario|ordenante|origen)\s*:\s*([^\n.]+)/i;
// Palabras en mayúsculas después de "en", "de" o "a"; cada palabra termina en espacio, puntuación o fin de texto
const PATRON_MAYUSCULAS = /(?:^|\s)(?:[Ee]n|[Dd]e|a)\s+([A-Z][A-Z0-9&'*-]{2,}(?=[\s.,;]|$)(?:\s+[A-Z0-9&'*-]+(?=[\s.,;]|$))*)/;
const PATRON_OPERACION = /(?:n[uú]mero de operaci[oó]n|nro\.? de operaci[oó]n|c[oó]digo de operaci[oó]n)\s*:?\s*(\d{4,})/i;

function aNumero(texto) {
  if (texto.includes(',') && texto.includes('.')) {
    texto = texto.lastIndexOf(',') > texto.lastIndexOf('.')
      ? texto.replace(/\./g, '').replace(',', '.')   // 1.250,00
      : texto.replace(/,/g, '');                      // 1,250.00
  } else if (texto.includes(',')) {
    const decimales = texto.split(',').pop();
    texto = (texto.split(',').length === 2 && decimales.length === 2)
      ? texto.replace(',', '.')                       // 45,90
      : texto.replace(/,/g, '');                      // 1,250
  }
  return parseFloat(texto);
}

function detectarTipo(asunto, cuerpo) {
  for (const texto of [asunto, cuerpo]) {
    for (const [tipo, patron] of TIPOS) {
      if (patron.test(texto)) return tipo;
    }
  }
  return 'Otro';
}

function detectarContraparte(cuerpo) {
  const encontrado = cuerpo.match(PATRON_ETIQUETA) || cuerpo.match(PATRON_MAYUSCULAS);
  return encontrado ? encontrado[1].trim().replace(/^[ .,;]+|[ .,;]+$/g, '').slice(0, 60) : '';
}

/** Devuelve los datos del movimiento, o null si el correo no es un movimiento realizado. */
function extraer(asunto, cuerpo) {
  if (NO_MOVIMIENTO.test(asunto)) return null;
  const monto = cuerpo.match(PATRON_MONTO) || asunto.match(PATRON_MONTO);
  if (!monto) return null;
  const tipo = detectarTipo(asunto, cuerpo);
  if (tipo === 'Otro') return null;
  const operacion = cuerpo.match(PATRON_OPERACION);
  return {
    tipo: tipo,
    sentido: INGRESOS.includes(tipo) ? 'Ingreso' : 'Egreso',
    monto: aNumero(monto[2]),
    moneda: MONEDAS[monto[1]],
    contraparte: detectarContraparte(cuerpo),
    operacion: operacion ? operacion[1] : '',
  };
}

// ---------- Lectura de Gmail con permiso de solo lectura (equivale a src/gmail_client.py) ----------

function decodificar(data) {
  let bytes;
  if (Array.isArray(data)) {
    bytes = data;  // el servicio de Gmail de Apps Script ya entrega el contenido como bytes
  } else {
    // Base64 "web-safe" sin relleno: se convierte a base64 estándar y se completa con "="
    const texto = String(data).replace(/-/g, '+').replace(/_/g, '/');
    bytes = Utilities.base64Decode(texto + '='.repeat((4 - texto.length % 4) % 4));
  }
  return Utilities.newBlob(bytes).getDataAsString('UTF-8');
}

function partes(parte, tipo) {
  if (parte.mimeType === tipo && parte.body && parte.body.data) return [decodificar(parte.body.data)];
  return (parte.parts || []).reduce((acc, sub) => acc.concat(partes(sub, tipo)), []);
}

function htmlATexto(contenido) {
  return contenido
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<br\s*\/?>|<\/p>|<\/tr>|<\/div>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/[ \t\u00a0]+/g, ' ')
    .trim();
}

function buscarIds(consulta) {
  const ids = [];
  let pagina;
  do {
    const respuesta = Gmail.Users.Messages.list('me', { q: consulta, maxResults: 100, pageToken: pagina });
    (respuesta.messages || []).forEach(m => ids.push(m.id));
    pagina = respuesta.nextPageToken;
  } while (pagina && ids.length < 500);
  return ids;
}

function leerCorreo(id) {
  const mensaje = Gmail.Users.Messages.get('me', id, { format: 'full' });
  const cabeceras = {};
  (mensaje.payload.headers || []).forEach(c => { cabeceras[c.name.toLowerCase()] = c.value; });
  const textos = partes(mensaje.payload, 'text/plain');
  const cuerpo = textos.length ? textos.join('\n') : htmlATexto(partes(mensaje.payload, 'text/html').join('\n'));
  const fecha = new Date(Number(mensaje.internalDate));
  return {
    id: id,
    fecha: Utilities.formatDate(fecha, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss'),
    asunto: cabeceras.subject || '',
    cuerpo: cuerpo,
  };
}

// ---------- Proceso diario ----------

function registrarMovimientos() {
  const hoja = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.PESTANA);
  const total = hoja.getLastRow();
  const datos = total > 1 ? hoja.getRange(2, 1, total - 1, ENCABEZADOS.length).getValues() : [];
  const yaRegistrados = new Set(datos.map(fila => String(fila[COL.id_correo])));

  const nuevos = [];
  buscarIds(CONFIG.CONSULTA)
    .filter(id => !yaRegistrados.has(id))   // no se vuelve a registrar lo que ya está en la hoja
    .forEach(id => {
      const correo = leerCorreo(id);
      const mov = extraer(correo.asunto, correo.cuerpo);
      if (mov) nuevos.push(Object.assign({ fecha: correo.fecha, asunto: correo.asunto, id_correo: id }, mov));
    });

  nuevos.sort((a, b) => a.fecha.localeCompare(b.fecha));
  if (nuevos.length) {
    // Texto plano en fecha, operación e ID: evita que Sheets los convierta en números o fechas
    ['fecha', 'operacion', 'id_correo'].forEach(c =>
      hoja.getRange(2, COL[c] + 1, hoja.getMaxRows() - 1, 1).setNumberFormat('@'));
    const filas = nuevos.map(m => ENCABEZADOS.map(c => m[c]));
    hoja.getRange(total + 1, 1, filas.length, ENCABEZADOS.length).setValues(filas);
    ajustarAnchos(hoja);
  }

  enviarResumen(nuevos, datos.concat(nuevos.map(m => ENCABEZADOS.map(c => m[c]))));
}

function ajustarAnchos(hoja) {
  const visibles = COL.id_correo;  // la última columna (ID) está oculta
  hoja.autoResizeColumns(1, visibles);
  for (let c = 1; c <= visibles; c++) {
    hoja.setColumnWidth(c, Math.min(hoja.getColumnWidth(c) + 30, 700));  // margen para el botón de filtro
  }
}

// ---------- Resumen por correo (equivale a src/notificador.py) ----------

function formatoMonto(moneda, monto) {
  return (moneda === 'USD' ? 'US$ ' : 'S/ ') + Number(monto).toFixed(2);
}

function enviarResumen(nuevos, todas) {
  const zona = Session.getScriptTimeZone();
  const hoy = Utilities.formatDate(new Date(), zona, 'dd/MM/yyyy');
  const mes = Utilities.formatDate(new Date(), zona, 'yyyy-MM');

  const lineas = [`Movimientos nuevos desde la última revisión: ${nuevos.length}`, ''];
  nuevos.slice(0, 15).forEach(m => {
    const detalle = m.contraparte ? ` · ${m.contraparte}` : '';
    lineas.push(`- ${m.fecha.slice(0, 16)} · ${m.tipo} · ${formatoMonto(m.moneda, m.monto)}${detalle}`);
  });
  if (nuevos.length > 15) lineas.push(`... y ${nuevos.length - 15} más.`);
  if (!nuevos.length) lineas.push('No hubo movimientos nuevos.');

  const totales = {};
  todas.filter(f => String(f[COL.fecha]).startsWith(mes)).forEach(f => {
    const clave = `${f[COL.sentido]}|${f[COL.moneda]}`;
    totales[clave] = (totales[clave] || 0) + Number(f[COL.monto]);
  });
  lineas.push('', 'Totales del mes actual:');
  const claves = Object.keys(totales).sort().reverse();
  if (!claves.length) lineas.push('- Sin movimientos registrados este mes.');
  claves.forEach(clave => {
    const [sentido, moneda] = clave.split('|');
    lineas.push(`- ${sentido}s: ${formatoMonto(moneda, totales[clave])}`);
  });

  lineas.push('', `Hoja completa: ${SpreadsheetApp.getActiveSpreadsheet().getUrl()}`,
              '', 'Enviado automáticamente por tu script de registro de movimientos (Apps Script).');
  MailApp.sendEmail(Session.getEffectiveUser().getEmail(),
                    `Resumen de movimientos bancarios – ${hoy}: ${nuevos.length} nuevo(s)`,
                    lineas.join('\n'));
}

// ---------- Configuración (ejecutar una sola vez) ----------

/** Crea el activador diario. Si ya existía, lo reemplaza (no se duplica). */
function crearActivadorDiario() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'registrarMovimientos')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('registrarMovimientos').timeBased().everyDays(1).atHour(CONFIG.HORA_DEL_RESUMEN).create();
}