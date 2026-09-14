import { PrinterAdapter, normalizeCapabilities } from './printer-adapter.js';
import {
  getBambuStatus,
  listBambuFiles,
  uploadBambuFile,
  verifyBambuFile,
  startBambuFile,
  setBambuJobState,
  setBambuTemperatures,
  setBambuFans
} from '../bambu-api.js';
import { discoverBambuPrinters } from '../bambu-discovery.js';
import { createBambuCameraSource } from '../bambu-camera.js';

export const BAMBU_LAB_ADAPTER_TYPE = 'bambu-lab';

const MODEL_PROFILES = Object.freeze({
  P1S: Object.freeze({ model:'P1S', nozzleMax:300, bedMax:100, toolCount:1, cameraTransport:'p1-jpeg' }),
  P2S: Object.freeze({ model:'P2S', nozzleMax:300, bedMax:110, toolCount:1, cameraTransport:'rtsps' }),
  H2S: Object.freeze({ model:'H2S', nozzleMax:350, bedMax:120, toolCount:1, cameraTransport:'rtsps' }),
  H2D: Object.freeze({ model:'H2D', nozzleMax:350, bedMax:120, toolCount:2, cameraTransport:'rtsps' }),
  H2C: Object.freeze({ model:'H2C', nozzleMax:350, bedMax:120, toolCount:2, cameraTransport:'rtsps' })
});

function cleanHost(host) {
  return String(host || '').trim().replace(/^https?:\/\//i, '').replace(/\/$/, '').replace(/:\d+$/, '');
}

export function bambuModelProfile(model) {
  const key = String(model || '').trim().toUpperCase();
  return MODEL_PROFILES[key] || null;
}

export function prepareBambuConfig(input = {}) {
  const name = String(input.name || '').trim();
  const host = cleanHost(input.host);
  const model = String(input.model || input.adapterConfig?.model || '').trim().toUpperCase();
  const serialNumber = String(input.serialNumber || input.adapterConfig?.serialNumber || '').trim();
  const accessCode = String(input.accessCode || input.adapterConfig?.accessCode || '').trim();
  const profile = bambuModelProfile(model);
  if (!name || !host) throw new Error('name and host are required');
  if (!profile) throw new Error('Bambu model must be P1S, P2S, H2S, H2D, or H2C');
  if (!serialNumber) throw new Error('Bambu serial number is required');
  if (!accessCode) throw new Error('Bambu LAN access code is required');
  if (!/^[a-zA-Z0-9._:-]+$/.test(host)) throw new Error('Host/IP contains invalid characters');
  if (serialNumber.length > 64 || /[\x00-\x1f\x7f]/.test(serialNumber)) throw new Error('Bambu serial number is invalid');
  if (accessCode.length > 128 || /[\x00-\x1f\x7f]/.test(accessCode)) throw new Error('Bambu LAN access code is invalid');
  return {
    name,
    host,
    adapterType:BAMBU_LAB_ADAPTER_TYPE,
    manufacturer:'Bambu Lab',
    model:profile.model,
    serialNumber,
    checkCode:'',
    adapterConfig:{ accessCode }
  };
}

function capabilitiesFor(profile) {
  return normalizeCapabilities({
    status:true,
    localFiles:true,
    fileUpload:true,
    printLocalFile:true,
    jobControl:true,
    nozzleTemperature:true,
    toolTemperatures:profile.toolCount > 1,
    bedTemperature:true,
    coolingFan:true,
    chamberFan:true,
    filtration:false,
    bedLeveling:false,
    levelBeforePrint:true,
    camera:true,
    chamberPreheat:false,
    chamberTemperatureSensor:true,
    materialStatus:true,
    materialDesignation:false,
    nozzleDesignation:false,
    printToolMapping:false,
    nativeMultiMaterialWorkflow:true,
    projectFileMappingReview:true,
    flowCalibrationBeforePrint:true,
    timeLapseBeforePrint:true,
    autoFilamentReplenishment:false,
    filamentEntanglementDetection:false,
    toolheadNozzleStatus:true,
    toolheadOffsetCalibration:false
  });
}

export class BambuLabAdapter extends PrinterAdapter {
  constructor(printer) {
    super(printer);
    this.profile = bambuModelProfile(printer.model);
    if (!this.profile) throw new Error(`Unsupported Bambu Lab model: ${printer.model || 'unknown'}`);
    this._capabilities = capabilitiesFor(this.profile);
  }
  get type() { return BAMBU_LAB_ADAPTER_TYPE; }
  get manufacturer() { return 'Bambu Lab'; }
  get model() { return this.profile.model; }
  get capabilities() { return this._capabilities; }
  get uploadExtensions() { return ['.gcode', '.3mf']; }
  get limits() {
    return Object.freeze({
      bedTemperature:{ min:0, max:this.profile.bedMax },
      nozzleTemperature:{ min:0, max:this.profile.nozzleMax },
      coolingFan:{ min:0, max:100 },
      chamberFan:{ min:0, max:100 },
      toolCount:this.profile.toolCount
    });
  }

  async getStatus() { return getBambuStatus(this.printer, this.profile); }
  async getFiles() { return listBambuFiles(this.printer); }
  async uploadFile(filePath, options = {}) { return uploadBambuFile(this.printer, filePath, options); }
  async verifyFile(fileName) { return verifyBambuFile(this.printer, fileName); }
  async printLocalFile(fileName, options = {}) { return startBambuFile(this.printer, fileName, options, this.profile); }
  async setJobState(action) { return setBambuJobState(this.printer, action, this.profile); }
  async setTemperatures(values) { return setBambuTemperatures(this.printer, values, this.profile); }
  async setFans(values) { return setBambuFans(this.printer, values, this.profile); }
  async getCameraSource() { return createBambuCameraSource(this.printer); }
  async activateCamera() { return null; }
  fallbackCameraUrl() { return null; }
}

export const bambuLabAdapterDefinition = Object.freeze({
  type:BAMBU_LAB_ADAPTER_TYPE,
  manufacturer:'Bambu Lab',
  label:'Bambu Lab (P1S / P2S / H2S / H2D / H2C)',
  models:Object.keys(MODEL_PROFILES),
  capabilities:normalizeCapabilities({
    status:true, localFiles:true, fileUpload:true, printLocalFile:true, jobControl:true,
    nozzleTemperature:true, bedTemperature:true, coolingFan:true, chamberFan:true,
    levelBeforePrint:true, camera:true, chamberTemperatureSensor:true, materialStatus:true,
    nativeMultiMaterialWorkflow:true, projectFileMappingReview:true, flowCalibrationBeforePrint:true, timeLapseBeforePrint:true,
    toolheadNozzleStatus:true
  }),
  configFields:[
    { name:'model', label:'Bambu model', required:true, placeholder:'P1S, P2S, H2S, H2D, or H2C', help:'Enter the exact printer model. Discovery normally fills this automatically.' },
    { name:'serialNumber', label:'Printer serial number', required:true, placeholder:'Printer serial number', help:'Shown in Bambu Studio / printer settings and also discovered automatically on the LAN.' },
    { name:'accessCode', label:'LAN access code', required:true, secret:true, placeholder:'LAN access code', help:'Enable LAN/Developer Mode on the printer and enter its LAN access code. The code stays on the controller backend and is never sent to the browser.' }
  ],
  discover:discoverBambuPrinters,
  prepareConfig:prepareBambuConfig,
  create:(printer) => new BambuLabAdapter(printer)
});
