import { promises as fs } from 'node:fs';
import path from 'node:path';
import { parseGcodeMaterialMetadata } from './file-material-metadata.js';

const MAX_CHUNK_BYTES = 256 * 1024;

function clean(value) {
  const text = String(value ?? '').trim().replace(/^['"]|['"]$/g, '').trim();
  return text || null;
}

function splitList(value) {
  return String(value ?? '')
    .split(/\s*[;,]\s*/)
    .map(clean)
    .filter(Boolean);
}

function numberList(value) {
  return splitList(value).map((item) => {
    const number = Number.parseFloat(item);
    return Number.isFinite(number) ? number : null;
  });
}

function normalizeColor(value) {
  const text = String(value || '').trim().replace(/^0x/i, '').replace(/^#/, '').toUpperCase();
  if (/^[0-9A-F]{8}$/.test(text)) return `#${text.slice(2)}`;
  if (/^[0-9A-F]{6}$/.test(text)) return `#${text}`;
  return null;
}

function parseConfig(text) {
  const values = new Map();
  for (const line of String(text || '').split(/\r?\n/)) {
    const match = line.match(/^\s*;?\s*([^:=]+?)\s*[:=]\s*(.*?)\s*$/);
    if (!match) continue;
    const key = match[1].trim().toLowerCase();
    if (!values.has(key)) values.set(key, match[2].trim());
  }
  return values;
}

function first(config, keys) {
  for (const key of keys) {
    if (config.has(key)) return config.get(key);
  }
  return null;
}

export function parseGcodePrintRequirements(text = '', { fileName = null } = {}) {
  const config = parseConfig(text);
  const materialMetadata = parseGcodeMaterialMetadata(text);
  const types = splitList(first(config, ['filament_type', 'filament_types']));
  const colors = splitList(first(config, ['filament_colour', 'filament_color', 'extruder_colour', 'extruder_color'])).map(normalizeColor);
  const nozzleDiameters = numberList(first(config, ['nozzle_diameter', 'nozzle_diameters']));
  const weights = numberList(first(config, ['filament used [g]', 'filament_used_g']));

  const referenced = new Set();
  for (let index = 0; index < weights.length; index++) {
    if (Number(weights[index]) > 0) referenced.add(index);
  }
  for (const line of String(text || '').split(/\r?\n/)) {
    const code = line.split(';')[0].trim();
    const match = code.match(/^T(\d+)\b/i);
    if (match) referenced.add(Number(match[1]));
  }

  let usageReliable = referenced.size > 0;
  if (!referenced.size) {
    const detectedCount = Math.max(types.length, colors.length, nozzleDiameters.length, materialMetadata.materials?.length || 0, 1);
    for (let index = 0; index < detectedCount; index++) referenced.add(index);
    usageReliable = detectedCount === 1;
  }

  const requiredTools = [...referenced].filter((index) => Number.isInteger(index) && index >= 0).sort((a, b) => a - b);
  const logicalTools = requiredTools.map((index) => ({
    index,
    material: clean(types[index] ?? (types.length === 1 ? types[0] : null) ?? (materialMetadata.materials?.length === 1 ? materialMetadata.materials[0] : null)),
    color: colors[index] ?? (colors.length === 1 ? colors[0] : null),
    nozzleDiameter: Number.isFinite(Number(nozzleDiameters[index]))
      ? Number(nozzleDiameters[index])
      : (nozzleDiameters.length === 1 && Number.isFinite(Number(nozzleDiameters[0])) ? Number(nozzleDiameters[0]) : null)
  }));

  return {
    fileName: fileName ? String(fileName) : null,
    requiredTools,
    toolCount: requiredTools.length,
    logicalTools,
    usageReliable,
    materialMetadata,
    source: 'gcode-bounded-scan',
    warning: usageReliable ? null : 'The file did not expose reliable used-tool metadata; detected palette entries are treated as possible tools.'
  };
}

export async function readFilePrintRequirements(filePath, { maxChunkBytes = MAX_CHUNK_BYTES } = {}) {
  const extension = path.extname(String(filePath || '')).toLowerCase();
  if (!['.gcode', '.gx', '.g'].includes(extension)) {
    return {
      fileName: path.basename(String(filePath || '')) || null,
      requiredTools: [],
      toolCount: 0,
      logicalTools: [],
      usageReliable: false,
      materialMetadata: {
        metadataAvailable: false,
        requiredMaterial: null,
        materials: [],
        source: null,
        warning: 'Material metadata is unavailable for this file type.'
      },
      source: null,
      warning: 'Automatic compatibility requirements are not currently inspected for this file type.'
    };
  }

  const handle = await fs.open(filePath, 'r');
  try {
    const stat = await handle.stat();
    const headSize = Math.min(stat.size, maxChunkBytes);
    const tailSize = Math.min(Math.max(0, stat.size - headSize), maxChunkBytes);
    const head = Buffer.alloc(headSize);
    if (headSize) await handle.read(head, 0, headSize, 0);
    let tail = Buffer.alloc(0);
    if (tailSize) {
      tail = Buffer.alloc(tailSize);
      await handle.read(tail, 0, tailSize, Math.max(0, stat.size - tailSize));
    }
    return parseGcodePrintRequirements(`${head.toString('utf8')}\n${tail.toString('utf8')}`, { fileName:path.basename(filePath) });
  } finally {
    await handle.close();
  }
}
