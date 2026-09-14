import dgram from 'node:dgram';

const SUPPORTED_MODELS = new Set(['P1S','P2S','H2S','H2D','H2C']);
const MODEL_CODES = new Map([
  ['C12','P1S'],
  ['N7','P2S'],
  ['O1S','H2S'],
  ['O1D','H2D'],
  ['O1C','H2C'],
  ['O1C2','H2C']
]);
const SERIAL_PREFIXES = [
  ['01P','P1S'],
  ['22E','P2S'],
  ['093','H2S'],
  ['31B8','H2C']
];

export function parseBambuSsdpPacket(value) {
  const text = Buffer.isBuffer(value) ? value.toString('utf8') : String(value || '');
  if (!/urn:bambulab-com:device:3dprinter:1/i.test(text)) return null;
  const headers = {};
  for (const line of text.split(/\r?\n/).slice(1)) {
    const index = line.indexOf(':');
    if (index <= 0) continue;
    headers[line.slice(0, index).trim().toLowerCase()] = line.slice(index + 1).trim();
  }
  const host = String(headers.location || '').replace(/^https?:\/\//i, '').replace(/\/.*$/, '').trim();
  const serialNumber = String(headers.usn || '').trim();
  const modelCode = String(headers['devmodel.bambu.com'] || '').trim().toUpperCase();
  const name = String(headers['devname.bambu.com'] || '').trim();
  let model = MODEL_CODES.get(modelCode) || null;
  if (!model) {
    const upperName = name.toUpperCase();
    model = [...SUPPORTED_MODELS].find((candidate) => upperName.includes(candidate)) || null;
  }
  if (!model) {
    const upperSerial = serialNumber.toUpperCase();
    const prefix = SERIAL_PREFIXES.find(([value]) => upperSerial.startsWith(value));
    model = prefix?.[1] || null;
  }
  // Legacy H2 serials share the 094 prefix, so use the advertised model code/name
  // rather than guessing H2S/H2D/H2C from that prefix.
  if (!host || !serialNumber || !model || !SUPPORTED_MODELS.has(model)) return null;
  return {
    name:name || `Bambu Lab ${model}`,
    host,
    manufacturer:'Bambu Lab',
    model,
    serialNumber,
    modelCode:modelCode || null,
    firmwareVersion:String(headers['devversion.bambu.com'] || '').trim() || null,
    adapterType:'bambu-lab'
  };
}

export async function discoverBambuPrinters({ timeoutMs = 2200 } = {}) {
  const sockets = [];
  const found = new Map();
  const listen = (port) => new Promise((resolve) => {
    const socket = dgram.createSocket({ type:'udp4', reuseAddr:true });
    sockets.push(socket);
    socket.on('message', (message) => {
      const printer = parseBambuSsdpPacket(message);
      if (printer) found.set(printer.serialNumber, printer);
    });
    socket.on('error', () => resolve());
    socket.bind(port, '0.0.0.0', () => resolve());
  });
  await Promise.all([listen(1990), listen(2021)]);
  await new Promise((resolve) => setTimeout(resolve, timeoutMs));
  for (const socket of sockets) {
    try { socket.close(); } catch {}
  }
  return [...found.values()];
}
