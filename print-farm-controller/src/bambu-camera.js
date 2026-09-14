import tls from 'node:tls';
import { execFile, spawn } from 'node:child_process';

function accessCode(printer) {
  return String(printer?.adapterConfig?.accessCode || '').trim();
}

function serialNumber(printer) {
  return String(printer?.serialNumber || '').trim();
}

function authPacket(printer) {
  const packet = Buffer.alloc(80);
  packet.writeUInt32LE(0x40, 0);
  packet.writeUInt32LE(0x3000, 4);
  packet.writeUInt32LE(0, 8);
  packet.writeUInt32LE(0, 12);
  Buffer.from('bblp', 'ascii').copy(packet, 16, 0, 32);
  Buffer.from(accessCode(printer), 'ascii').copy(packet, 48, 0, 32);
  return packet;
}

export class P1SnapshotSource {
  constructor(printer) {
    this.printer = printer;
    this.socket = null;
    this.buffer = Buffer.alloc(0);
    this.frameLength = null;
    this.latest = null;
    this.waiters = new Set();
    this.intervalMs = 2000;
    this.sourceLabel = `${printer.host}:6000 Bambu chamber camera`;
    this.kind = 'snapshot';
  }

  async start() {
    if (this.socket && !this.socket.destroyed) return;
    if (!accessCode(this.printer)) throw new Error('Bambu LAN access code is required for camera access');
    const socket = tls.connect({
      host:this.printer.host,
      port:6000,
      rejectUnauthorized:false,
      servername:serialNumber(this.printer) || undefined
    });
    this.socket = socket;
    socket.on('data', (chunk) => this.onData(chunk));
    socket.on('error', (error) => this.fail(error));
    socket.on('close', () => this.fail(new Error('Bambu camera connection closed')));
    await Promise.race([
      new Promise((resolve, reject) => { socket.once('secureConnect', resolve); socket.once('error', reject); }),
      new Promise((_, reject) => setTimeout(() => reject(new Error('Bambu camera connection timed out')), 7000))
    ]);
    socket.write(authPacket(this.printer));
  }

  onData(chunk) {
    this.buffer = Buffer.concat([this.buffer, chunk]);
    while (true) {
      if (this.frameLength === null) {
        if (this.buffer.length < 16) return;
        this.frameLength = this.buffer.readUInt32LE(0);
        this.buffer = this.buffer.subarray(16);
        if (!Number.isInteger(this.frameLength) || this.frameLength < 4 || this.frameLength > 20 * 1024 * 1024) {
          this.fail(new Error('Bambu camera returned an invalid frame length'));
          return;
        }
      }
      if (this.buffer.length < this.frameLength) return;
      const frame = Buffer.from(this.buffer.subarray(0, this.frameLength));
      this.buffer = this.buffer.subarray(this.frameLength);
      this.frameLength = null;
      if (frame[0] === 0xFF && frame[1] === 0xD8) {
        this.latest = frame;
        for (const waiter of this.waiters) waiter.resolve(frame);
        this.waiters.clear();
      }
    }
  }

  fail(error) {
    for (const waiter of this.waiters) waiter.reject(error);
    this.waiters.clear();
  }

  async waitForFirstSnapshot() {
    if (this.latest) return Buffer.from(this.latest);
    return new Promise((resolve, reject) => {
      const waiter = {
        resolve:(frame) => { clearTimeout(timer); this.waiters.delete(waiter); resolve(Buffer.from(frame)); },
        reject:(error) => { clearTimeout(timer); this.waiters.delete(waiter); reject(error); }
      };
      const timer = setTimeout(() => waiter.reject(new Error('Timed out waiting for Bambu camera frame')), 10000);
      this.waiters.add(waiter);
    });
  }

  async getSnapshot() {
    if (!this.socket || this.socket.destroyed) await this.start();
    if (this.latest) return Buffer.from(this.latest);
    return this.waitForFirstSnapshot();
  }

  async refresh() {
    await this.stop();
    await this.start();
  }

  async stop() {
    try { this.socket?.destroy(); } catch {}
    this.socket = null;
    this.buffer = Buffer.alloc(0);
    this.frameLength = null;
  }
}

function ffmpegAvailable(binary = 'ffmpeg') {
  return new Promise((resolve) => {
    execFile(binary, ['-version'], { timeout:4000 }, (error) => resolve(!error));
  });
}

export class RtspsSnapshotSource {
  constructor(printer) {
    this.printer = printer;
    this.intervalMs = 2500;
    this.sourceLabel = `${printer.host}:322 Bambu RTSPS camera`;
    this.ffmpeg = String(process.env.FFMPEG_PATH || 'ffmpeg');
    this.available = null;
    this.kind = 'snapshot';
  }

  async start() {
    if (!accessCode(this.printer)) throw new Error('Bambu LAN access code is required for camera access');
    if (this.available === null) this.available = await ffmpegAvailable(this.ffmpeg);
    if (!this.available) throw new Error('Bambu RTSPS camera requires ffmpeg in PATH (or FFMPEG_PATH)');
  }

  async waitForFirstSnapshot() { return this.getSnapshot(); }

  async getSnapshot() {
    await this.start();
    const code = encodeURIComponent(accessCode(this.printer));
    const url = `rtsps://bblp:${code}@${this.printer.host}:322/streaming/live/1`;
    return new Promise((resolve, reject) => {
      const child = spawn(this.ffmpeg, [
        '-hide_banner','-loglevel','error','-rtsp_transport','tcp','-tls_verify','0',
        '-i',url,'-frames:v','1','-f','image2pipe','-vcodec','mjpeg','pipe:1'
      ], { stdio:['ignore','pipe','pipe'] });
      const chunks = [];
      const errors = [];
      let total = 0;
      let settled = false;
      const finish = (fn, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        fn(value);
      };
      const timer = setTimeout(() => {
        child.kill('SIGKILL');
        finish(reject, new Error('Timed out reading Bambu RTSPS camera'));
      }, 10000);
      child.stdout.on('data', (chunk) => {
        total += chunk.length;
        if (total <= 20 * 1024 * 1024) chunks.push(Buffer.from(chunk));
      });
      child.stderr.on('data', (chunk) => errors.push(Buffer.from(chunk)));
      child.once('error', (error) => finish(reject, error));
      child.once('close', (codeValue) => {
        const frame = Buffer.concat(chunks);
        if (codeValue === 0 && frame.length > 4 && frame[0] === 0xFF && frame[1] === 0xD8) finish(resolve, frame);
        else finish(reject, new Error(`Bambu RTSPS snapshot failed${errors.length ? `: ${Buffer.concat(errors).toString('utf8').trim().slice(0, 240)}` : ''}`));
      });
    });
  }

  async refresh() { this.available = null; await this.start(); }
  async stop() {}
}

export function createBambuCameraSource(printer) {
  const model = String(printer?.model || '').trim().toUpperCase();
  return model === 'P1S' ? new P1SnapshotSource(printer) : new RtspsSnapshotSource(printer);
}
