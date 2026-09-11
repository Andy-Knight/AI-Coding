import { promises as fs } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { FLASHFORGE_AD5M_ADAPTER_TYPE } from './adapters/adapter-registry.js';

function defaultDataDir() {
  if (process.platform === 'win32') {
    const base = process.env.LOCALAPPDATA || process.env.APPDATA || os.homedir();
    return path.join(base, 'Print Controller', 'FlashForge Fleet');
  }

  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'Print Controller', 'FlashForge Fleet');
  }

  const base = process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local', 'share');
  return path.join(base, 'print-controller', 'flashforge-fleet');
}

const DATA_DIR = path.resolve(process.env.DATA_DIR || defaultDataDir());
const FILE_PATH = path.join(DATA_DIR, 'printers.json');

function normalizePrinterName(value) {
  const text = String(value ?? '').trim();
  if (!text) throw new Error('Printer name is required');
  if (text.length > 80) throw new Error('Printer name must be 80 characters or fewer');
  if (/[\x00-\x1f\x7f]/.test(text)) throw new Error('Printer name contains invalid characters');
  return text;
}

function normalizeMaterialDesignation(value) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  if (text.length > 48) throw new Error('Material designation must be 48 characters or fewer');
  if (/[\x00-\x1f\x7f]/.test(text)) throw new Error('Material designation contains invalid characters');
  return text;
}

async function ensureStore() {
  await fs.mkdir(DATA_DIR, { recursive: true });
  try {
    await fs.access(FILE_PATH);
  } catch {
    await fs.writeFile(FILE_PATH, '[]\n', { mode: 0o600 });
  }
}

function normalizeStoredPrinter(printer) {
  const adapterType = String(printer?.adapterType || FLASHFORGE_AD5M_ADAPTER_TYPE);
  return {
    ...printer,
    adapterType,
    manufacturer: printer?.manufacturer || (adapterType === FLASHFORGE_AD5M_ADAPTER_TYPE ? 'FlashForge' : 'Unknown'),
    model: printer?.model || (adapterType === FLASHFORGE_AD5M_ADAPTER_TYPE ? 'Adventurer 5M Pro' : 'Unknown')
  };
}

async function readAll() {
  await ensureStore();
  const raw = await fs.readFile(FILE_PATH, 'utf8');
  const printers = JSON.parse(raw || '[]');
  return Array.isArray(printers) ? printers.map(normalizeStoredPrinter) : [];
}

async function writeAll(printers) {
  await ensureStore();
  const temp = `${FILE_PATH}.tmp`;
  await fs.writeFile(temp, `${JSON.stringify(printers, null, 2)}\n`, { mode: 0o600 });
  await fs.rename(temp, FILE_PATH);
}

export async function listPrinters() {
  return readAll();
}

export async function getPrinter(id) {
  const printers = await readAll();
  return printers.find((printer) => printer.id === id) || null;
}

export async function addPrinter(input) {
  const printers = await readAll();
  const existingOrders = printers.map((printer) => Number(printer.dashboardOrder)).filter(Number.isFinite);
  const dashboardOrder = existingOrders.length === printers.length && printers.length
    ? Math.max(...existingOrders) + 1
    : undefined;
  const printer = {
    id: crypto.randomUUID(),
    name: normalizePrinterName(input.name),
    adapterType: String(input.adapterType || FLASHFORGE_AD5M_ADAPTER_TYPE),
    manufacturer: String(input.manufacturer || 'FlashForge'),
    model: String(input.model || 'Adventurer 5M Pro'),
    host: input.host.trim(),
    serialNumber: String(input.serialNumber || '').trim(),
    checkCode: String(input.checkCode || '').trim(),
    adapterConfig: input.adapterConfig && typeof input.adapterConfig === 'object' ? { ...input.adapterConfig } : {},
    httpPort: Number(input.httpPort || 8898),
    cameraPort: Number(input.cameraPort || 8080),
    tcpPort: Number(input.tcpPort || input.commandPort || 8899),
    ...(dashboardOrder !== undefined ? { dashboardOrder } : {}),
    createdAt: new Date().toISOString()
  };
  printers.push(printer);
  await writeAll(printers);
  return printer;
}

export async function renamePrinter(id, name) {
  const printers = await readAll();
  const index = printers.findIndex((printer) => printer.id === id);
  if (index < 0) return null;

  const nextName = normalizePrinterName(name);
  printers[index] = { ...printers[index], name: nextName };
  await writeAll(printers);
  return normalizeStoredPrinter(printers[index]);
}

export async function setPrinterMaterialDesignation(id, material) {
  const printers = await readAll();
  const index = printers.findIndex((printer) => printer.id === id);
  if (index < 0) return null;

  const designation = normalizeMaterialDesignation(material);
  const adapterConfig = { ...(printers[index].adapterConfig || {}) };
  if (designation) adapterConfig.filamentDesignation = designation;
  else delete adapterConfig.filamentDesignation;

  printers[index] = { ...printers[index], adapterConfig };
  await writeAll(printers);
  return normalizeStoredPrinter(printers[index]);
}

export async function reorderPrinters(printerIds) {
  const printers = await readAll();
  const requested = Array.isArray(printerIds) ? printerIds.map(String) : [];
  const currentIds = new Set(printers.map((printer) => printer.id));
  const unique = [...new Set(requested)];

  if (unique.length !== printers.length || unique.some((id) => !currentIds.has(id))) {
    throw new Error('Printer order must include every configured printer exactly once');
  }

  const order = new Map(unique.map((id, index) => [id, index]));
  const updated = printers.map((printer) => ({ ...printer, dashboardOrder: order.get(printer.id) }));
  await writeAll(updated);
  return updated;
}

export async function removePrinter(id) {
  const printers = await readAll();
  const next = printers.filter((printer) => printer.id !== id);
  if (next.length === printers.length) return false;
  await writeAll(next);
  return true;
}

export function publicPrinter(printer) {
  return {
    id: printer.id,
    name: printer.name,
    adapterType: printer.adapterType || FLASHFORGE_AD5M_ADAPTER_TYPE,
    manufacturer: printer.manufacturer || 'Unknown',
    model: printer.model || 'Unknown',
    host: printer.host,
    serialNumber: printer.serialNumber,
    httpPort: printer.httpPort,
    cameraPort: printer.cameraPort,
    tcpPort: printer.tcpPort || printer.commandPort || 8899,
    dashboardOrder: Number.isFinite(Number(printer.dashboardOrder)) ? Number(printer.dashboardOrder) : null,
    materialDesignation: String(printer.adapterConfig?.filamentDesignation || '').trim() || null,
    createdAt: printer.createdAt
  };
}

export const printerStorePath = FILE_PATH;
