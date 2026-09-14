import tls from 'node:tls';
import path from 'node:path';
import { createReadStream, promises as fs } from 'node:fs';

const MQTT_PORT = 8883;
const FTPS_PORT = 990;
const MQTT_KEEPALIVE_SECONDS = 30;
const COMMAND_TIMEOUT_MS = 7000;
const STATUS_TIMEOUT_MS = 8000;
const FULL_REFRESH_MS = 5 * 60 * 1000;

export class BambuApiError extends Error {
  constructor(message, { cause = null } = {}) {
    super(message, { cause });
    this.name = 'BambuApiError';
  }
}

function accessCode(printer) {
  return String(printer?.adapterConfig?.accessCode || '').trim();
}

function serialNumber(printer) {
  return String(printer?.serialNumber || printer?.adapterConfig?.serialNumber || '').trim();
}

function mqttString(value) {
  const payload = Buffer.from(String(value ?? ''), 'utf8');
  const prefix = Buffer.alloc(2);
  prefix.writeUInt16BE(payload.length, 0);
  return Buffer.concat([prefix, payload]);
}

function encodeRemainingLength(length) {
  const bytes = [];
  let value = Number(length);
  do {
    let encoded = value % 128;
    value = Math.floor(value / 128);
    if (value > 0) encoded |= 0x80;
    bytes.push(encoded);
  } while (value > 0);
  return Buffer.from(bytes);
}

function mqttPacket(typeFlags, payload = Buffer.alloc(0)) {
  return Buffer.concat([Buffer.from([typeFlags]), encodeRemainingLength(payload.length), payload]);
}

function connectPacket(printer) {
  const code = accessCode(printer);
  const serial = serialNumber(printer);
  if (!code) throw new BambuApiError('Bambu LAN access code is required');
  if (!serial) throw new BambuApiError('Bambu serial number is required');
  const variable = Buffer.concat([
    mqttString('MQTT'),
    Buffer.from([4, 0xC2]),
    Buffer.from([0, MQTT_KEEPALIVE_SECONDS])
  ]);
  const payload = Buffer.concat([
    mqttString(`printfleet-${serial.slice(-8)}-${process.pid}`),
    mqttString('bblp'),
    mqttString(code)
  ]);
  return mqttPacket(0x10, Buffer.concat([variable, payload]));
}

function subscribePacket(packetId, topic) {
  const id = Buffer.alloc(2);
  id.writeUInt16BE(packetId, 0);
  return mqttPacket(0x82, Buffer.concat([id, mqttString(topic), Buffer.from([0])]));
}

function publishPacket(topic, payload) {
  return mqttPacket(0x30, Buffer.concat([mqttString(topic), Buffer.from(payload)]));
}

function readRemainingLength(buffer, offset = 1) {
  let multiplier = 1;
  let value = 0;
  let consumed = 0;
  let byte;
  do {
    if (offset + consumed >= buffer.length || consumed >= 4) return null;
    byte = buffer[offset + consumed];
    value += (byte & 0x7F) * multiplier;
    multiplier *= 128;
    consumed += 1;
  } while (byte & 0x80);
  return { value, consumed };
}

function mergeDeep(target, source) {
  if (!source || typeof source !== 'object' || Array.isArray(source)) return source;
  const result = target && typeof target === 'object' && !Array.isArray(target) ? { ...target } : {};
  for (const [key, value] of Object.entries(source)) {
    if (value && typeof value === 'object' && !Array.isArray(value)) result[key] = mergeDeep(result[key], value);
    else result[key] = value;
  }
  return result;
}

function numeric(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeHex(value) {
  const text = String(value ?? '').trim().replace(/^#/, '').replace(/^0x/i, '').toUpperCase();
  if (/^[0-9A-F]{8}$/.test(text)) return `#${text.slice(0, 6)}`;
  if (/^[0-9A-F]{6}$/.test(text)) return `#${text}`;
  return null;
}

function unpackPackedTemperature(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return { actual:null, target:null };
  if (n > 0xFFFF) return { actual:n & 0xFFFF, target:(n >>> 16) & 0xFFFF };
  return { actual:n, target:null };
}

function normalizeState(value) {
  const state = String(value || 'IDLE').trim().toUpperCase();
  if (state === 'RUNNING' || state === 'PREPARE') return state === 'RUNNING' ? 'printing' : 'heating';
  if (state === 'PAUSE' || state === 'PAUSED') return 'paused';
  if (state === 'FAILED') return 'error';
  return 'idle';
}

function findActiveTray(print = {}) {
  const ams = print.ams || {};
  const trayNow = Number(ams.tray_now);
  const units = Array.isArray(ams.ams) ? ams.ams : [];
  if (Number.isInteger(trayNow) && trayNow >= 0 && trayNow < 254) {
    const unitId = Math.floor(trayNow / 4);
    const trayId = trayNow % 4;
    const unit = units.find((entry) => Number(entry.id) === unitId) || units[unitId];
    const tray = Array.isArray(unit?.tray) ? (unit.tray.find((entry) => Number(entry.id) === trayId) || unit.tray[trayId]) : null;
    if (tray) return tray;
  }
  return ams.vt_tray || print.vt_tray || null;
}

function normalizeFilament(print = {}) {
  const tray = findActiveTray(print);
  if (!tray) return { present:null, metadataAvailable:false, materialSource:null, material:null, materialVariant:null, color:null };
  const material = String(tray.tray_type || tray.type || '').trim() || null;
  const color = normalizeHex(tray.tray_color || tray.color);
  const present = material || color ? true : null;
  return {
    present,
    metadataAvailable:Boolean(material || color),
    materialSource:'printer',
    material,
    materialVariant:String(tray.tray_sub_brands || tray.sub_brands || '').trim() || null,
    color,
    vendor:String(tray.tray_info_idx || '').trim() || null
  };
}

function normalizeExtruderTools(print = {}, modelProfile = {}) {
  const extruder = print.device?.extruder || {};
  const info = Array.isArray(extruder.info) ? extruder.info : [];
  const nozzleInfo = Array.isArray(print.device?.nozzle?.info) ? print.device.nozzle.info : [];
  const profileCount = Number(modelProfile.toolCount || 1);
  const count = Math.max(profileCount, info.length || 0, 1);
  const activeBits = Number(extruder.state);
  const activeIndex = Number.isFinite(activeBits) && info.length > 1 ? ((activeBits >> 4) & 0x0F) : 0;
  const baseFilament = normalizeFilament(print);
  const tools = [];
  for (let index = 0; index < count; index++) {
    const ex = info[index] || {};
    const packed = unpackPackedTemperature(ex.temp);
    const nozzle = nozzleInfo[index] || {};
    const fallbackActual = index === 0 ? numeric(print.nozzle_temper, 0) : 0;
    const fallbackTarget = index === 0 ? numeric(print.nozzle_target_temper, 0) : 0;
    const nozzleDiameter = Number(nozzle.diameter ?? nozzle.nozzle_diameter ?? (index === 0 ? print.nozzle_diameter : null));
    const bits = Number(ex.info);
    const filamentPresent = Number.isFinite(bits) ? Boolean(bits & 0x02) : (index === 0 ? baseFilament.present : null);
    tools.push({
      index,
      name:`T${index}`,
      actual:packed.actual ?? fallbackActual,
      target:packed.target ?? fallbackTarget,
      active:info.length > 1 ? activeIndex === index : index === 0,
      nozzleDiameter:Number.isFinite(nozzleDiameter) && nozzleDiameter > 0 ? nozzleDiameter : null,
      filament:index === 0 ? { ...baseFilament, present:filamentPresent } : {
        present:filamentPresent,
        metadataAvailable:false,
        materialSource:null,
        material:null,
        materialVariant:null,
        color:null
      }
    });
  }
  return tools;
}

export function normalizeBambuStatus(raw = {}, modelProfile = {}) {
  const print = raw.print || raw || {};
  const tools = normalizeExtruderTools(print, modelProfile);
  const activeTool = tools.find((tool) => tool.active) || tools[0];
  const ctc = unpackPackedTemperature(print.device?.ctc?.info?.temp);
  const chamberActual = ctc.actual ?? (Number.isFinite(Number(print.chamber_temper)) ? Number(print.chamber_temper) : null);
  const fileName = String(print.subtask_name || print.gcode_file || '').trim() || null;
  const progress = Math.max(0, Math.min(100, numeric(print.mc_percent, 0)));
  const state = normalizeState(print.gcode_state);
  const fan255 = (value) => Math.max(0, Math.min(100, Math.round(numeric(value, 0) / 255 * 100)));
  return {
    status:state,
    statusMessage:String(print.print_error || '') || '',
    firmwareVersion:raw.infoVersion || null,
    fileName:state === 'idle' && ['FINISH','IDLE'].includes(String(print.gcode_state || '').toUpperCase()) ? null : fileName,
    progress,
    currentLayer:numeric(print.layer_num, 0),
    totalLayers:numeric(print.total_layer_num, 0),
    remainingSeconds:Math.max(0, numeric(print.mc_remaining_time, 0) * 60),
    elapsedSeconds:0,
    activeTool:Number(activeTool?.index || 0),
    nozzle:{ actual:numeric(activeTool?.actual, 0), target:numeric(activeTool?.target, 0) },
    tools,
    materials:{
      available:tools.some((tool) => tool.filament?.metadataAvailable || tool.filament?.present !== null),
      loadedCount:tools.filter((tool) => tool.filament?.present === true).length,
      toolCount:tools.length,
      metadataCount:tools.filter((tool) => tool.filament?.metadataAvailable).length,
      tools:tools.map((tool) => tool.filament)
    },
    bed:{ actual:numeric(print.bed_temper, 0), target:numeric(print.bed_target_temper, 0) },
    chamber:{ actual:chamberActual, target:ctc.target },
    coolingFan:fan255(print.cooling_fan_speed),
    chamberFan:fan255(print.big_fan2_speed ?? print.big_fan1_speed),
    auxiliaryFan:fan255(print.big_fan1_speed),
    cameraAvailable:true,
    speedLevel:Number.isFinite(Number(print.spd_lvl)) ? Number(print.spd_lvl) : null,
    wifiSignal:String(print.wifi_signal || '').trim() || null,
    rawGcodeState:String(print.gcode_state || '').trim() || null
  };
}

class BambuMqttSession {
  constructor(printer, modelProfile = {}) {
    this.printer = printer;
    this.modelProfile = modelProfile;
    this.socket = null;
    this.buffer = Buffer.alloc(0);
    this.readyPromise = null;
    this.readyResolve = null;
    this.readyReject = null;
    this.ready = false;
    this.state = {};
    this.infoVersion = null;
    this.lastStatusAt = 0;
    this.lastFullRequestAt = 0;
    this.sequence = 0;
    this.pending = new Map();
    this.statusWaiters = new Set();
    this.keepalive = null;
    this.closed = false;
    this.reportTopic = `device/${serialNumber(printer)}/report`;
    this.requestTopic = `device/${serialNumber(printer)}/request`;
  }

  async ensureReady() {
    if (this.ready && this.socket && !this.socket.destroyed) return;
    if (this.readyPromise) return this.readyPromise;
    this.readyPromise = new Promise((resolve, reject) => {
      this.readyResolve = resolve;
      this.readyReject = reject;
      const timer = setTimeout(() => reject(new BambuApiError(`Timed out connecting to Bambu MQTT at ${this.printer.host}:${MQTT_PORT}`)), STATUS_TIMEOUT_MS);
      const finish = (fn, value) => { clearTimeout(timer); fn(value); };
      this.readyResolve = () => finish(resolve);
      this.readyReject = (error) => finish(reject, error);
    }).finally(() => { this.readyPromise = null; });

    const code = accessCode(this.printer);
    const serial = serialNumber(this.printer);
    if (!code || !serial) throw new BambuApiError('Bambu serial number and LAN access code are required');

    this.socket = tls.connect({
      host:this.printer.host,
      port:MQTT_PORT,
      rejectUnauthorized:false,
      servername:serial || undefined
    });
    this.socket.setNoDelay(true);
    this.socket.on('secureConnect', () => {
      try { this.socket.write(connectPacket(this.printer)); } catch (error) { this.fail(error); }
    });
    this.socket.on('data', (chunk) => this.onData(chunk));
    this.socket.on('error', (error) => this.fail(error));
    this.socket.on('close', () => this.fail(new BambuApiError('Bambu MQTT connection closed')));
    return this.readyPromise;
  }

  fail(error) {
    const wrapped = error instanceof BambuApiError ? error : new BambuApiError(error?.message || 'Bambu MQTT failure', { cause:error });
    this.ready = false;
    this.readyReject?.(wrapped);
    this.readyReject = null;
    this.readyResolve = null;
    for (const pending of this.pending.values()) pending.reject(wrapped);
    this.pending.clear();
    for (const waiter of this.statusWaiters) waiter.reject(wrapped);
    this.statusWaiters.clear();
    if (this.keepalive) clearInterval(this.keepalive);
    this.keepalive = null;
  }

  onData(chunk) {
    this.buffer = Buffer.concat([this.buffer, chunk]);
    while (this.buffer.length >= 2) {
      const remaining = readRemainingLength(this.buffer, 1);
      if (!remaining) return;
      const headerLength = 1 + remaining.consumed;
      const total = headerLength + remaining.value;
      if (this.buffer.length < total) return;
      const first = this.buffer[0];
      const payload = this.buffer.subarray(headerLength, total);
      this.buffer = this.buffer.subarray(total);
      this.handlePacket(first >> 4, payload);
    }
  }

  handlePacket(type, payload) {
    if (type === 2) {
      if (payload.length < 2 || payload[1] !== 0) {
        this.fail(new BambuApiError(`Bambu MQTT authentication failed (CONNACK ${payload[1] ?? 'unknown'})`));
        return;
      }
      this.socket.write(subscribePacket(1, this.reportTopic));
      return;
    }
    if (type === 9) {
      this.ready = true;
      this.readyResolve?.();
      this.readyResolve = null;
      this.readyReject = null;
      this.keepalive = setInterval(() => {
        if (this.socket && !this.socket.destroyed) this.socket.write(Buffer.from([0xC0, 0x00]));
      }, 20000);
      this.keepalive.unref?.();
      this.requestFull().catch(() => {});
      this.sendEnvelope({ info:{ command:'get_version' } }, { waitAck:false }).catch(() => {});
      return;
    }
    if (type !== 3 || payload.length < 2) return;
    const topicLength = payload.readUInt16BE(0);
    if (payload.length < 2 + topicLength) return;
    const body = payload.subarray(2 + topicLength).toString('utf8');
    let message;
    try { message = JSON.parse(body); } catch { return; }
    this.handleMessage(message);
  }

  handleMessage(message = {}) {
    const versionModules = message.info?.module;
    if (Array.isArray(versionModules)) {
      const ota = versionModules.find((entry) => String(entry.name || '').toLowerCase() === 'ota') || versionModules[0];
      if (ota?.sw_ver) this.infoVersion = String(ota.sw_ver);
    }

    for (const value of Object.values(message)) {
      if (!value || typeof value !== 'object') continue;
      const sequenceId = String(value.sequence_id ?? '');
      if (sequenceId && this.pending.has(sequenceId) && value.result !== undefined) {
        const pending = this.pending.get(sequenceId);
        this.pending.delete(sequenceId);
        if (String(value.result).toLowerCase() === 'success') pending.resolve(value);
        else pending.reject(new BambuApiError(`Bambu command failed${value.reason ? `: ${value.reason}` : ''}`));
      }
    }

    if (message.print && message.print.result === undefined) {
      this.state.print = mergeDeep(this.state.print, message.print);
      this.lastStatusAt = Date.now();
      for (const waiter of this.statusWaiters) waiter.resolve();
      this.statusWaiters.clear();
    }
  }

  async sendEnvelope(envelope, { waitAck = true } = {}) {
    await this.ensureReady();
    const rootKey = Object.keys(envelope)[0];
    if (!rootKey) throw new BambuApiError('Empty Bambu MQTT command');
    const sequenceId = String(++this.sequence);
    const body = { ...envelope[rootKey], sequence_id:sequenceId };
    const payload = JSON.stringify({ [rootKey]:body });
    let ack = null;
    if (waitAck) {
      ack = new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          this.pending.delete(sequenceId);
          reject(new BambuApiError('Bambu command was not acknowledged. Confirm LAN/Developer Mode is enabled.'));
        }, COMMAND_TIMEOUT_MS);
        this.pending.set(sequenceId, {
          resolve:(value) => { clearTimeout(timer); resolve(value); },
          reject:(error) => { clearTimeout(timer); reject(error); }
        });
      });
    }
    this.socket.write(publishPacket(this.requestTopic, Buffer.from(payload, 'utf8')));
    return waitAck ? ack : { sequenceId };
  }

  async requestFull() {
    this.lastFullRequestAt = Date.now();
    return this.sendEnvelope({ pushing:{ command:'pushall', version:1, push_target:1 } }, { waitAck:false });
  }

  async waitForStatus(timeoutMs = STATUS_TIMEOUT_MS) {
    if (this.lastStatusAt && this.state.print) return;
    return new Promise((resolve, reject) => {
      const waiter = {
        resolve:() => { clearTimeout(timer); this.statusWaiters.delete(waiter); resolve(); },
        reject:(error) => { clearTimeout(timer); this.statusWaiters.delete(waiter); reject(error); }
      };
      const timer = setTimeout(() => waiter.reject(new BambuApiError('No Bambu status report received. Confirm LAN/Developer Mode and serial number.')), timeoutMs);
      this.statusWaiters.add(waiter);
    });
  }

  async getStatus() {
    await this.ensureReady();
    if (!this.lastStatusAt || Date.now() - this.lastFullRequestAt > FULL_REFRESH_MS) await this.requestFull();
    if (!this.lastStatusAt) await this.waitForStatus();
    return normalizeBambuStatus({ ...this.state, infoVersion:this.infoVersion }, this.modelProfile);
  }
}

const mqttSessions = new Map();
function sessionKey(printer) {
  return `${printer.host}|${serialNumber(printer)}|${accessCode(printer)}`;
}

function sessionFor(printer, modelProfile = {}) {
  const key = sessionKey(printer);
  let session = mqttSessions.get(key);
  if (!session) {
    session = new BambuMqttSession(printer, modelProfile);
    mqttSessions.set(key, session);
  } else {
    session.printer = printer;
    session.modelProfile = modelProfile;
  }
  return session;
}

export async function getBambuStatus(printer, modelProfile = {}) {
  return sessionFor(printer, modelProfile).getStatus();
}

export async function sendBambuCommand(printer, envelope, modelProfile = {}) {
  return sessionFor(printer, modelProfile).sendEnvelope(envelope);
}

export async function setBambuJobState(printer, action, modelProfile = {}) {
  const normalized = String(action || '').trim().toLowerCase();
  const command = normalized === 'cancel' ? 'stop' : normalized;
  if (!['pause','resume','stop'].includes(command)) throw new BambuApiError(`Unsupported Bambu job action: ${action}`);
  return sendBambuCommand(printer, { print:{ command, param:'' } }, modelProfile);
}

function temperatureValue(value, max, label) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0 || n > max) throw new BambuApiError(`${label} must be 0-${max} °C`);
  return Math.round(n);
}

export async function setBambuTemperatures(printer, values = {}, modelProfile = {}) {
  const lines = [];
  if (values.bed !== undefined) lines.push(`M140 S${temperatureValue(values.bed, Number(modelProfile.bedMax || 120), 'Bed')}`);
  if (values.nozzle !== undefined) {
    const temp = temperatureValue(values.nozzle, Number(modelProfile.nozzleMax || 350), 'Nozzle');
    const toolIndex = values.toolIndex === undefined || values.toolIndex === null ? null : Number(values.toolIndex);
    if (toolIndex !== null) {
      if (!Number.isInteger(toolIndex) || toolIndex < 0 || toolIndex >= Number(modelProfile.toolCount || 1)) throw new BambuApiError('Tool index is out of range');
      lines.push(`M104 S${temp} T${toolIndex}`);
    } else lines.push(`M104 S${temp}`);
  }
  if (!lines.length) throw new BambuApiError('No temperature value supplied');
  return sendBambuCommand(printer, { print:{ command:'gcode_line', param:`${lines.join('\n')}\n` } }, modelProfile);
}

function fanGcode(fan, percent) {
  const n = Number(percent);
  if (!Number.isFinite(n) || n < 0 || n > 100) throw new BambuApiError(`${fan} fan must be 0-100%`);
  const pwm = Math.round(n / 100 * 255);
  if (fan === 'cooling') return `M106 P1 S${pwm}`;
  if (fan === 'auxiliary') return `M106 P2 S${pwm}`;
  return `M106 P3 S${pwm}`;
}

export async function setBambuFans(printer, values = {}, modelProfile = {}) {
  const lines = [];
  if (values.coolingFan !== undefined) lines.push(fanGcode('cooling', values.coolingFan));
  if (values.chamberFan !== undefined) lines.push(fanGcode('chamber', values.chamberFan));
  if (!lines.length) throw new BambuApiError('No supported fan value supplied');
  return sendBambuCommand(printer, { print:{ command:'gcode_line', param:`${lines.join('\n')}\n` } }, modelProfile);
}

export async function startBambuFile(printer, fileName, options = {}, modelProfile = {}) {
  const name = path.posix.basename(String(fileName || '').replace(/\\/g, '/'));
  if (!name) throw new BambuApiError('File name is required');
  if (/\.3mf$/i.test(name)) {
    const payload = {
      command:'project_file',
      param:'Metadata/plate_1.gcode',
      project_id:'0', profile_id:'0', task_id:'0', subtask_id:'0',
      subtask_name:name.replace(/\.gcode\.3mf$/i, '').replace(/\.3mf$/i, ''),
      file:`/${name}`,
      url:`ftp:///${name}`,
      md5:'',
      timelapse:Boolean(options.timeLapseBeforePrint),
      bed_type:'auto',
      bed_leveling:options.levelingBeforePrint !== false,
      bed_levelling:options.levelingBeforePrint !== false,
      flow_cali:Boolean(options.flowCalibrationBeforePrint),
      vibration_cali:true,
      layer_inspect:true,
      use_ams:Boolean(options.useAms),
      ams_mapping:Array.isArray(options.amsMapping) ? options.amsMapping : []
    };
    return sendBambuCommand(printer, { print:payload }, modelProfile);
  }
  if (!/\.gcode$/i.test(name)) throw new BambuApiError('Bambu local print start supports .gcode and .3mf files');
  return sendBambuCommand(printer, { print:{ command:'gcode_file', param:name } }, modelProfile);
}

class FtpsControl {
  constructor(printer) {
    this.printer = printer;
    this.socket = null;
    this.buffer = '';
    this.currentMulti = null;
    this.waiters = [];
    this.responses = [];
  }

  async connect() {
    const code = accessCode(this.printer);
    if (!code) throw new BambuApiError('Bambu LAN access code is required');
    this.socket = tls.connect({ host:this.printer.host, port:FTPS_PORT, rejectUnauthorized:false, servername:serialNumber(this.printer) || undefined });
    this.socket.setEncoding('utf8');
    this.socket.on('data', (chunk) => this.onData(chunk));
    this.socket.on('error', (error) => this.fail(error));
    await Promise.race([
      new Promise((resolve, reject) => { this.socket.once('secureConnect', resolve); this.socket.once('error', reject); }),
      new Promise((_, reject) => setTimeout(() => reject(new BambuApiError('Bambu FTPS connection timed out')), COMMAND_TIMEOUT_MS))
    ]);
    let reply = await this.nextReply();
    if (reply.code !== 220) throw new BambuApiError(`Bambu FTPS returned ${reply.code}`);
    reply = await this.command('USER bblp');
    if (reply.code === 331) reply = await this.command(`PASS ${code}`);
    if (reply.code !== 230) throw new BambuApiError('Bambu FTPS authentication failed');
    await this.expect(this.command('PBSZ 0'), [200]);
    await this.expect(this.command('PROT P'), [200]);
    await this.expect(this.command('TYPE I'), [200]);
  }

  fail(error) {
    const wrapped = error instanceof BambuApiError ? error : new BambuApiError(error?.message || 'Bambu FTPS failure', { cause:error });
    while (this.waiters.length) this.waiters.shift().reject(wrapped);
  }

  onData(chunk) {
    this.buffer += chunk;
    while (true) {
      const idx = this.buffer.indexOf('\r\n');
      if (idx < 0) break;
      const line = this.buffer.slice(0, idx);
      this.buffer = this.buffer.slice(idx + 2);
      this.handleLine(line);
    }
  }

  handleLine(line) {
    if (this.currentMulti) {
      this.currentMulti.lines.push(line);
      if (line.startsWith(`${this.currentMulti.code} `)) {
        const response = { code:Number(this.currentMulti.code), text:this.currentMulti.lines.join('\n') };
        this.currentMulti = null;
        this.pushResponse(response);
      }
      return;
    }
    const match = line.match(/^(\d{3})([ -])(.*)$/);
    if (!match) return;
    if (match[2] === '-') this.currentMulti = { code:match[1], lines:[line] };
    else this.pushResponse({ code:Number(match[1]), text:match[3] });
  }

  pushResponse(response) {
    const waiter = this.waiters.shift();
    if (waiter) waiter.resolve(response);
    else this.responses.push(response);
  }

  nextReply() {
    if (this.responses.length) return Promise.resolve(this.responses.shift());
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const idx = this.waiters.findIndex((entry) => entry.resolve === wrappedResolve);
        if (idx >= 0) this.waiters.splice(idx, 1);
        reject(new BambuApiError('Timed out waiting for Bambu FTPS response'));
      }, COMMAND_TIMEOUT_MS);
      const wrappedResolve = (value) => { clearTimeout(timer); resolve(value); };
      this.waiters.push({ resolve:wrappedResolve, reject:(error) => { clearTimeout(timer); reject(error); } });
    });
  }

  async command(command) {
    this.socket.write(`${command}\r\n`);
    return this.nextReply();
  }

  async expect(promise, codes) {
    const reply = await promise;
    if (!codes.includes(reply.code)) throw new BambuApiError(`Bambu FTPS command failed (${reply.code} ${reply.text})`);
    return reply;
  }

  async passiveSocket() {
    const reply = await this.expect(this.command('EPSV'), [229]);
    const match = reply.text.match(/\(\|\|\|(\d+)\|\)/);
    if (!match) throw new BambuApiError('Bambu FTPS returned an invalid EPSV response');
    const port = Number(match[1]);
    const socket = tls.connect({
      host:this.printer.host,
      port,
      rejectUnauthorized:false,
      servername:serialNumber(this.printer) || undefined,
      session:this.socket.getSession?.()
    });
    await Promise.race([
      new Promise((resolve, reject) => { socket.once('secureConnect', resolve); socket.once('error', reject); }),
      new Promise((_, reject) => setTimeout(() => reject(new BambuApiError('Bambu FTPS data connection timed out')), COMMAND_TIMEOUT_MS))
    ]);
    return socket;
  }

  close() {
    try { this.socket?.end('QUIT\r\n'); } catch {}
    try { this.socket?.destroy(); } catch {}
  }
}

export async function listBambuFiles(printer) {
  const control = new FtpsControl(printer);
  try {
    await control.connect();
    const data = await control.passiveSocket();
    const chunks = [];
    data.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
    const ended = new Promise((resolve, reject) => { data.once('end', resolve); data.once('close', resolve); data.once('error', reject); });
    const first = await control.command('NLST');
    if (![125,150].includes(first.code)) throw new BambuApiError(`Bambu file listing failed (${first.code})`);
    await ended;
    await control.expect(control.nextReply(), [226,250]);
    const files = Buffer.concat(chunks).toString('utf8').split(/\r?\n/)
      .map((value) => value.trim().replace(/^\/+/, ''))
      .filter((value) => /\.(?:gcode|3mf)$/i.test(value))
      .sort((a, b) => a.localeCompare(b, undefined, { numeric:true, sensitivity:'base' }));
    return { files:[...new Set(files)], complete:true, source:'bambu-ftps', ordering:'alphabetical', warning:null };
  } finally {
    control.close();
  }
}

export async function uploadBambuFile(printer, filePath, { fileName = null } = {}) {
  const stats = await fs.stat(filePath);
  if (!stats.isFile()) throw new BambuApiError('Upload source is not a file');
  const remoteName = path.posix.basename(String(fileName || path.basename(filePath)).replace(/\\/g, '/'));
  if (!/\.(?:gcode|3mf)$/i.test(remoteName)) throw new BambuApiError('Bambu upload supports .gcode and .3mf files');
  const control = new FtpsControl(printer);
  try {
    await control.connect();
    const data = await control.passiveSocket();
    const first = await control.command(`STOR ${remoteName}`);
    if (![125,150].includes(first.code)) throw new BambuApiError(`Bambu upload was refused (${first.code} ${first.text})`);
    await new Promise((resolve, reject) => {
      const source = createReadStream(filePath);
      source.once('error', reject);
      data.once('error', reject);
      data.once('close', resolve);
      source.pipe(data);
    });
    await control.expect(control.nextReply(), [226,250]);
    return { ok:true, fileName:remoteName, size:stats.size, source:'bambu-ftps' };
  } finally {
    control.close();
  }
}

export async function verifyBambuFile(printer, fileName) {
  const wanted = path.posix.basename(String(fileName || '').replace(/\\/g, '/')).toLocaleLowerCase();
  try {
    const listing = await listBambuFiles(printer);
    const verified = listing.files.some((entry) => path.posix.basename(entry).toLocaleLowerCase() === wanted);
    return { verified, source:'bambu-ftps', ...(!verified ? { warning:'Upload completed, but the file was not visible in Bambu printer storage.' } : {}) };
  } catch (error) {
    return { verified:false, source:null, warning:`Bambu file verification failed: ${error.message}` };
  }
}
