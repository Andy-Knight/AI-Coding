import test from 'node:test';
import assert from 'node:assert/strict';
import { PrintQueueService } from '../src/print-queue.js';

class FakeFleetState {
  constructor(states = []) {
    this.states = new Map(states.map((state) => [state.id, state]));
    this.subscribers = new Set();
  }
  subscribe(callback) {
    this.subscribers.add(callback);
    callback(this.getFleet());
    return () => this.subscribers.delete(callback);
  }
  getFleet() { return [...this.states.values()]; }
  getPrinterState(id) { return this.states.get(id) || null; }
  async refreshNow() {}
  setState(id, patch) {
    const current = this.states.get(id) || { id };
    this.states.set(id, { ...current, ...patch });
    for (const callback of this.subscribers) callback(this.getFleet());
  }
}

function memoryStore(initial = []) {
  let jobs = structuredClone(initial);
  return {
    load: async () => structuredClone(jobs),
    save: async (next) => { jobs = structuredClone(next); },
    read: () => structuredClone(jobs)
  };
}

async function waitFor(predicate, timeoutMs = 500) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.fail('Timed out waiting for condition');
}

test('queued print starts on an idle printer and records completion', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', online:true, status:{ status:'idle', fileName:null, progress:0 } }]);
  const store = memoryStore();
  const starts = [];
  const printer = { id:'p1', name:'U1', adapterType:'test' };
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async (id) => id === 'p1' ? printer : null,
    adapterResolver: () => ({
      capabilities:{ printLocalFile:true, jobControl:true },
      getStatus: async () => fleetState.getPrinterState('p1').status,
      printLocalFile: async (fileName, options) => starts.push({ fileName, options }),
      setJobState: async () => {}
    }),
    loadJobsFn: store.load,
    saveJobsFn: store.save,
    minActiveMs: 0
  });
  await service.start();
  const queued = await service.add({ printerId:'p1', fileName:'part.gcode', options:{ levelingBeforePrint:false } });
  await waitFor(() => starts.length === 1);
  assert.equal(starts[0].fileName, 'part.gcode');
  assert.equal(starts[0].options.levelingBeforePrint, false);
  assert.equal(service.getJob(queued.id).status, 'starting');

  fleetState.setState('p1', { online:true, status:{ status:'printing', fileName:'part.gcode', progress:37 } });
  await waitFor(() => service.getJob(queued.id).status === 'printing');
  assert.equal(service.getJob(queued.id).maxProgress, 37);

  fleetState.setState('p1', { online:true, status:{ status:'idle', fileName:null, progress:100 } });
  await waitFor(() => service.getJob(queued.id).status === 'completed');
  assert.ok(service.getJob(queued.id).finishedAt);
  service.stop();
});

test('printer busy with a manual print blocks queue progression', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', online:true, status:{ status:'printing', fileName:'manual.gcode', progress:50 } }]);
  const store = memoryStore();
  let starts = 0;
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async () => ({ id:'p1', name:'Printer' }),
    adapterResolver: () => ({ capabilities:{ printLocalFile:true }, printLocalFile:async () => { starts++; } }),
    loadJobsFn: store.load,
    saveJobsFn: store.save
  });
  await service.start();
  const job = await service.add({ printerId:'p1', fileName:'queued.gcode' });
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(starts, 0);
  assert.equal(service.getJob(job.id).status, 'queued');
  service.stop();
});

test('queue reorder validates all queued jobs and preserves requested order', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', online:false, status:null }]);
  const store = memoryStore();
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async () => ({ id:'p1', name:'Printer' }),
    adapterResolver: () => ({ capabilities:{ printLocalFile:true } }),
    loadJobsFn: store.load,
    saveJobsFn: store.save
  });
  await service.start();
  const a = await service.add({ printerId:'p1', fileName:'a.gcode' });
  const b = await service.add({ printerId:'p1', fileName:'b.gcode' });
  const c = await service.add({ printerId:'p1', fileName:'c.gcode' });
  await service.reorder([c.id, a.id, b.id]);
  assert.deepEqual(service.getSnapshot().jobs.filter((job) => job.status === 'queued').map((job) => job.fileName), ['c.gcode','a.gcode','b.gcode']);
  await assert.rejects(() => service.reorder([a.id]), /every queued job/);
  service.stop();
});

test('cancelling an active queued print also cancels the printer job', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', online:false, status:null }]);
  const store = memoryStore();
  const cancellations = [];
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async () => ({ id:'p1', name:'Printer' }),
    adapterResolver: () => ({ capabilities:{ printLocalFile:true, jobControl:true }, setJobState:async (action) => cancellations.push(action) }),
    loadJobsFn: store.load,
    saveJobsFn: store.save
  });
  await service.start();
  const job = await service.add({ printerId:'p1', fileName:'part.gcode' });
  service.jobs.find((item) => item.id === job.id).status = 'printing';
  await service.cancel(job.id);
  assert.deepEqual(cancellations, ['cancel']);
  assert.equal(service.getJob(job.id).status, 'cancelled');
  assert.equal(service.getSnapshot().awaitingClearance, 1);
  service.stop();
});

test('queued U1 mapped print refuses to start if a mapped tool changes after queueing', async () => {
  const fleetState = new FakeFleetState([{
    id:'u1', online:true, status:{ status:'printing', fileName:'other.gcode', tools:[
      { index:0, nozzleDiameter:0.4, filament:{ present:true, color:'#FF0000', material:'PLA' } },
      { index:1, nozzleDiameter:0.4, filament:{ present:true, color:'#00FF00', material:'PETG' } }
    ] }
  }]);
  const store = memoryStore();
  let starts = 0;
  let freshTools = [
    { index:0, nozzleDiameter:0.6, filament:{ present:true, color:'#FF0000', material:'PLA' } },
    { index:1, nozzleDiameter:0.4, filament:{ present:true, color:'#00FF00', material:'PETG' } }
  ];
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async () => ({ id:'u1', name:'U1' }),
    adapterResolver: () => ({
      capabilities:{ printLocalFile:true, printToolMapping:true },
      getStatus:async () => ({ status:'idle', tools:freshTools }),
      printLocalFile:async () => { starts++; }
    }),
    loadJobsFn: store.load,
    saveJobsFn: store.save
  });
  await service.start();
  const job = await service.add({
    printerId:'u1',
    fileName:'multi.gcode',
    options:{ toolMap:{ 0:0 }, usedLogicalTools:[0] }
  });
  fleetState.setState('u1', { online:true, status:{ status:'idle', fileName:null, tools:fleetState.getPrinterState('u1').status.tools } });
  await waitFor(() => service.getJob(job.id).status === 'failed');
  assert.equal(starts, 0);
  assert.match(service.getJob(job.id).error, /nozzle changed from 0\.4 mm/);
  service.stop();
});

test('completed queued print blocks the next job until bed clearance is confirmed', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', online:false, status:null }]);
  const store = memoryStore();
  const starts = [];
  const printer = { id:'p1', name:'Printer' };
  const adapter = {
    capabilities:{ printLocalFile:true, jobControl:true },
    getStatus: async () => fleetState.getPrinterState('p1').status,
    printLocalFile: async (fileName) => starts.push(fileName),
    setJobState: async () => {}
  };
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async () => printer,
    adapterResolver: () => adapter,
    loadJobsFn: store.load,
    saveJobsFn: store.save,
    minActiveMs: 0
  });
  await service.start();
  const first = await service.add({ printerId:'p1', fileName:'first.gcode' });
  const second = await service.add({ printerId:'p1', fileName:'second.gcode' });

  fleetState.setState('p1', { online:true, status:{ status:'idle', fileName:null, progress:0 } });
  await waitFor(() => starts.length === 1);
  assert.deepEqual(starts, ['first.gcode']);

  fleetState.setState('p1', { online:true, status:{ status:'printing', fileName:'first.gcode', progress:50 } });
  await waitFor(() => service.getJob(first.id).status === 'printing');
  fleetState.setState('p1', { online:true, status:{ status:'idle', fileName:null, progress:100 } });
  await waitFor(() => service.getJob(first.id).status === 'completed');
  await new Promise((resolve) => setTimeout(resolve, 30));

  assert.deepEqual(starts, ['first.gcode']);
  assert.equal(service.getJob(second.id).status, 'queued');
  assert.equal(service.getSnapshot().awaitingClearance, 1);
  assert.equal(service.getSnapshot().bedClearance[0].printerId, 'p1');

  await service.clearBed('p1');
  await waitFor(() => starts.length === 2);
  assert.deepEqual(starts, ['first.gcode', 'second.gcode']);
  assert.equal(service.getSnapshot().awaitingClearance, 0);
  service.stop();
});

test('bed-clearance interlock survives restart and cannot be erased by clearing history', async () => {
  const pending = {
    id:'done-1', printerId:'p1', printerName:'Printer', fileName:'finished.gcode', status:'completed',
    options:{}, queuedAt:'2026-09-10T12:00:00.000Z', startedAt:'2026-09-10T12:01:00.000Z',
    finishedAt:'2026-09-10T12:30:00.000Z', updatedAt:'2026-09-10T12:30:00.000Z',
    bedClearanceRequired:true, bedClearedAt:null
  };
  const queued = {
    id:'queued-1', printerId:'p1', printerName:'Printer', fileName:'next.gcode', status:'queued',
    options:{}, queuedAt:'2026-09-10T12:31:00.000Z', updatedAt:'2026-09-10T12:31:00.000Z'
  };
  const store = memoryStore([pending, queued]);
  const fleetState = new FakeFleetState([{ id:'p1', online:true, status:{ status:'idle', fileName:null } }]);
  let starts = 0;
  const makeService = () => new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async () => ({ id:'p1', name:'Printer' }),
    adapterResolver: () => ({
      capabilities:{ printLocalFile:true },
      getStatus:async () => ({ status:'idle', fileName:null }),
      printLocalFile:async () => { starts++; }
    }),
    loadJobsFn: store.load,
    saveJobsFn: store.save
  });

  const firstService = makeService();
  await firstService.start();
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(starts, 0);
  assert.equal(firstService.getSnapshot().awaitingClearance, 1);
  assert.equal(await firstService.clearHistory(), 0);
  firstService.stop();

  const secondService = makeService();
  await secondService.start();
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(starts, 0);
  assert.equal(secondService.getSnapshot().awaitingClearance, 1);
  await secondService.clearBed('p1');
  await waitFor(() => starts === 1);
  secondService.stop();
});

test('cancelling a waiting queue item does not create a bed-clearance requirement', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', online:false, status:null }]);
  const store = memoryStore();
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async () => ({ id:'p1', name:'Printer' }),
    adapterResolver: () => ({ capabilities:{ printLocalFile:true } }),
    loadJobsFn: store.load,
    saveJobsFn: store.save
  });
  await service.start();
  const job = await service.add({ printerId:'p1', fileName:'never-started.gcode' });
  await service.cancel(job.id, { cancelPrinter:false });
  assert.equal(service.getSnapshot().awaitingClearance, 0);
  assert.equal(service.getJob(job.id).bedClearanceRequired, false);
  service.stop();
});


test('FlashForge queued material mismatch becomes Needs review and blocks later jobs', async () => {
  const fleetState = new FakeFleetState([{ id:'ff', online:false, status:null }]);
  const store = memoryStore();
  const starts = [];
  const printer = { id:'ff', name:'FlashForge', adapterType:'flashforge-ad5m', adapterConfig:{ filamentDesignation:'ASA-CF' } };
  const metadata = {
    'first.gcode': { metadataAvailable:true, requiredMaterial:'PETG', materials:['PETG'], source:'filament_type' },
    'second.gcode': { metadataAvailable:true, requiredMaterial:'ASA-CF', materials:['ASA-CF'], source:'filament_type' }
  };
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async () => printer,
    adapterResolver: () => ({
      capabilities:{ printLocalFile:true },
      getStatus:async () => ({ status:'idle', fileName:null }),
      printLocalFile:async (fileName) => starts.push(fileName)
    }),
    getFileMaterialMetadataFn: async (_printerId, fileName) => metadata[fileName] || null,
    loadJobsFn: store.load,
    saveJobsFn: store.save
  });
  await service.start();
  const first = await service.add({ printerId:'ff', fileName:'first.gcode' });
  const second = await service.add({ printerId:'ff', fileName:'second.gcode' });
  fleetState.setState('ff', { online:true, status:{ status:'idle', fileName:null } });
  await waitFor(() => service.getJob(first.id).status === 'needs_review');
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(starts.length, 0);
  assert.equal(service.getJob(second.id).status, 'queued');
  assert.match(service.getJob(first.id).error, /file requires PETG/i);
  assert.equal(service.getSnapshot().needsReview, 1);

  printer.adapterConfig.filamentDesignation = 'petg';
  await service.recheck(first.id);
  await waitFor(() => starts.length === 1);
  assert.deepEqual(starts, ['first.gcode']);
  service.stop();
});

test('automatic queue job selects a compatible idle printer, uploads, verifies and applies U1 tool mapping', async () => {
  const tools = [
    { index:0, nozzleDiameter:0.6, filament:{ present:true, color:'#00FF00', material:'PETG' } },
    { index:2, nozzleDiameter:0.4, filament:{ present:true, color:'#FF0000', material:'PLA' } }
  ];
  const fleetState = new FakeFleetState([
    { id:'u1a', name:'U1-01', online:true, capabilities:{}, limits:{ toolCount:4 }, status:{ status:'idle', fileName:null, tools } },
    { id:'u1b', name:'U1-02', online:true, capabilities:{}, limits:{ toolCount:4 }, status:{ status:'idle', fileName:null, tools } }
  ]);
  const pendingClearance = {
    id:'old', assignmentMode:'fixed', printerId:'u1a', printerName:'U1-01', fileName:'old.gcode', status:'completed', options:{},
    queuedAt:'2026-09-11T10:00:00.000Z', updatedAt:'2026-09-11T10:30:00.000Z', finishedAt:'2026-09-11T10:30:00.000Z',
    bedClearanceRequired:true, bedClearedAt:null
  };
  const store = memoryStore([pendingClearance]);
  const uploaded = new Set();
  const uploads = [];
  const starts = [];
  const staged = {
    id:'11111111-1111-4111-8111-111111111111', fileName:'multi.gcode', filePath:'/staged/multi.gcode', size:123,
    sha256:'a'.repeat(64), stagedAt:'2026-09-11T11:00:00.000Z',
    requirements:{ requiredTools:[0,1], toolCount:2, usageReliable:true, logicalTools:[
      { index:0, material:'PLA', color:'#FF0000', nozzleDiameter:0.4 },
      { index:1, material:'PETG', color:'#00FF00', nozzleDiameter:0.6 }
    ], materialMetadata:{ metadataAvailable:true, requiredMaterial:null, materials:['PLA','PETG'] } }
  };
  const printers = new Map([
    ['u1a',{ id:'u1a', name:'U1-01' }],
    ['u1b',{ id:'u1b', name:'U1-02' }]
  ]);
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async (id) => printers.get(id) || null,
    adapterResolver: (printer) => ({
      capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true, printToolMapping:true },
      limits:{ toolCount:4 },
      getStatus:async () => fleetState.getPrinterState(printer.id).status,
      verifyFile:async () => ({ verified:uploaded.has(printer.id), source:'test' }),
      uploadFile:async (filePath) => { uploads.push({ id:printer.id, filePath }); uploaded.add(printer.id); },
      printLocalFile:async (fileName, options) => starts.push({ id:printer.id, fileName, options })
    }),
    loadJobsFn: store.load,
    saveJobsFn: store.save,
    getQueueFileFn: async () => staged,
    pruneQueueFilesFn: async () => 0,
    saveFileMaterialMetadataFn: async () => {}
  });
  await service.start();
  const job = await service.add({ assignmentMode:'automatic', stagedFileId:staged.id });
  await waitFor(() => starts.length === 1);
  const current = service.getJob(job.id);
  assert.equal(current.printerId, 'u1b');
  assert.equal(current.status, 'starting');
  assert.deepEqual(uploads, [{ id:'u1b', filePath:'/staged/multi.gcode' }]);
  assert.deepEqual(starts[0].options.toolMap, { '0':2, '1':0 });
  assert.ok(current.compatibility.blocked.some((item) => item.printerId === 'u1a' && item.reasons.some((reason) => reason.code === 'bed_not_cleared')));
  service.stop();
});

test('automatic queue job remains queued and exposes why compatible printers are blocked', async () => {
  const fleetState = new FakeFleetState([
    { id:'p1', name:'Printer 1', online:false, error:'offline', status:null },
    { id:'p2', name:'Printer 2', online:true, status:{ status:'printing', fileName:'other.gcode', tools:[{ index:0, filament:{ material:'PLA' } }] } }
  ]);
  const store = memoryStore();
  const staged = {
    id:'22222222-2222-4222-8222-222222222222', fileName:'part.gcode', filePath:'/staged/part.gcode', size:10, sha256:'b'.repeat(64), stagedAt:new Date().toISOString(),
    requirements:{ requiredTools:[0], toolCount:1, usageReliable:true, logicalTools:[{ index:0, material:'PLA' }], materialMetadata:{ metadataAvailable:true, requiredMaterial:'PLA', materials:['PLA'] } }
  };
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async (id) => ({ id, name:id === 'p1' ? 'Printer 1' : 'Printer 2' }),
    adapterResolver: () => ({ capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true }, limits:{} }),
    loadJobsFn: store.load,
    saveJobsFn: store.save,
    getQueueFileFn: async () => staged,
    pruneQueueFilesFn: async () => 0
  });
  await service.start();
  const job = await service.add({ assignmentMode:'automatic', stagedFileId:staged.id });
  await waitFor(() => Boolean(service.getJob(job.id).compatibility));
  const current = service.getJob(job.id);
  assert.equal(current.status, 'queued');
  assert.equal(current.printerId, null);
  assert.equal(current.compatibility.ready.length, 0);
  assert.ok(current.compatibility.blocked.some((item) => item.reasons.some((reason) => reason.code === 'offline')));
  assert.ok(current.compatibility.blocked.some((item) => item.reasons.some((reason) => reason.code === 'busy')));
  service.stop();
});

test('cancelling an automatic job during staged upload cannot race into print start', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', name:'Printer', online:true, status:{ status:'idle', fileName:null, tools:[{ index:0, filament:{ material:'PLA' } }] } }]);
  const store = memoryStore();
  const staged = {
    id:'33333333-3333-4333-8333-333333333333', fileName:'part.gcode', filePath:'/staged/part.gcode', size:10, sha256:'c'.repeat(64), stagedAt:new Date().toISOString(),
    requirements:{ requiredTools:[0], toolCount:1, usageReliable:true, logicalTools:[{ index:0, material:'PLA' }], materialMetadata:{ metadataAvailable:true, requiredMaterial:'PLA', materials:['PLA'] } }
  };
  let releaseUpload;
  const uploadGate = new Promise((resolve) => { releaseUpload = resolve; });
  let uploaded = false;
  let starts = 0;
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn: async () => ({ id:'p1', name:'Printer' }),
    adapterResolver: () => ({
      capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true }, limits:{}, uploadExtensions:['.gcode'],
      getStatus:async () => fleetState.getPrinterState('p1').status,
      verifyFile:async () => ({ verified:uploaded, source:'test' }),
      uploadFile:async () => { await uploadGate; uploaded = true; },
      printLocalFile:async () => { starts++; }
    }),
    loadJobsFn: store.load,
    saveJobsFn: store.save,
    getQueueFileFn: async () => staged,
    pruneQueueFilesFn: async () => 0,
    saveFileMaterialMetadataFn: async () => {}
  });
  await service.start();
  const job = await service.add({ assignmentMode:'automatic', stagedFileId:staged.id });
  await waitFor(() => service.getJob(job.id).status === 'uploading');
  await service.cancel(job.id);
  releaseUpload();
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(service.getJob(job.id).status, 'cancelled');
  assert.equal(starts, 0);
  assert.equal(service.getJob(job.id).bedClearanceRequired, false);
  service.stop();
});

test('clearing history immediately prunes unreferenced staged files but keeps files still referenced', async () => {
  const orphanId = '44444444-4444-4444-8444-444444444444';
  const sharedId = '55555555-5555-4555-8555-555555555555';
  const jobs = [
    {
      id:'done-orphan', assignmentMode:'automatic', printerId:'p1', printerName:'Printer', fileName:'orphan.gcode',
      stagedFile:{ id:orphanId, fileName:'orphan.gcode' }, status:'completed', options:{}, queuedAt:'2026-09-11T10:00:00.000Z',
      updatedAt:'2026-09-11T10:30:00.000Z', finishedAt:'2026-09-11T10:30:00.000Z', bedClearanceRequired:false, bedClearedAt:null
    },
    {
      id:'done-shared', assignmentMode:'automatic', printerId:'p1', printerName:'Printer', fileName:'shared.gcode',
      stagedFile:{ id:sharedId, fileName:'shared.gcode' }, status:'completed', options:{}, queuedAt:'2026-09-11T10:00:00.000Z',
      updatedAt:'2026-09-11T10:30:00.000Z', finishedAt:'2026-09-11T10:30:00.000Z', bedClearanceRequired:false, bedClearedAt:null
    },
    {
      id:'review-shared', assignmentMode:'automatic', printerId:null, printerName:'Next available compatible printer', fileName:'shared.gcode',
      stagedFile:{ id:sharedId, fileName:'shared.gcode' }, status:'needs_review', options:{}, queuedAt:'2026-09-11T10:31:00.000Z',
      updatedAt:'2026-09-11T10:31:00.000Z', bedClearanceRequired:false, bedClearedAt:null
    }
  ];
  const store = memoryStore(jobs);
  const pruneCalls = [];
  const service = new PrintQueueService({
    fleetState:new FakeFleetState([]),
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    loadJobsFn:store.load,
    saveJobsFn:store.save,
    pruneQueueFilesFn:async (referencedIds, options) => { pruneCalls.push({ referencedIds:[...referencedIds], options }); return 0; }
  });
  await service.start();
  pruneCalls.length = 0;

  assert.equal(await service.clearHistory(), 2);
  assert.deepEqual(service.getSnapshot().jobs.map((job) => job.id), ['review-shared']);
  assert.equal(pruneCalls.length, 2);
  assert.deepEqual(pruneCalls[0], { referencedIds:[sharedId], options:undefined });
  assert.deepEqual(pruneCalls[1], { referencedIds:[sharedId], options:{ minAgeMs:0 } });
  service.stop();
});
