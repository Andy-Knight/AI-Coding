from pathlib import Path

queue_path = Path('print-farm-controller/src/print-queue.js')
text = queue_path.read_text()

old = """      const active = runs.filter((job) => ACTIVE_QUEUE_STATES.has(job.status)).length;\n      const quantity = Math.max(runs.length, ...runs.map((job) => Number(job.productionQuantity || 0)));\n"""
new = """      const active = runs.filter((job) => ACTIVE_QUEUE_STATES.has(job.status)).length;\n      const cancelable = runs.filter((job) => ['queued', 'needs_review', 'uploading', 'preflight'].includes(job.status)).length;\n      const quantity = Math.max(runs.length, ...runs.map((job) => Number(job.productionQuantity || 0)));\n"""
if old not in text: raise SystemExit('aggregate active anchor not found')
text = text.replace(old, new, 1)

old = """        cancelled,\n        remaining: queued + needsReview,\n        paused,\n"""
new = """        cancelled,\n        remaining: queued + needsReview,\n        cancelable,\n        paused,\n"""
if old not in text: raise SystemExit('aggregate cancelable anchor not found')
text = text.replace(old, new, 1)

old = """    for (const job of jobs) {\n      if (!['queued', 'needs_review'].includes(job.status)) continue;\n      this.markTerminal(job, 'cancelled', null, { requireBedClearance:false });\n"""
new = """    for (const job of jobs) {\n      if (!['queued', 'needs_review', 'uploading', 'preflight'].includes(job.status)) continue;\n      this.markTerminal(job, 'cancelled', null, { requireBedClearance:false });\n"""
if old not in text: raise SystemExit('cancel production status anchor not found')
text = text.replace(old, new, 1)

old = """      throw new Error(`Production quantity cannot be below ${nonRemovable} because those copies have already started or finished`);\n"""
new = """      throw new Error(`Production quantity cannot be below ${nonRemovable} because those copies are already preparing, started, or finished`);\n"""
if old not in text: raise SystemExit('quantity error anchor not found')
text = text.replace(old, new, 1)

old = """      await this.ensureStagedFileAvailable(job, printer, adapter, { ...state, status:freshStatus });\n      if (TERMINAL_STATES.has(job.status)) return;\n\n      job.status = 'preflight';\n"""
new = """      await this.ensureStagedFileAvailable(job, printer, adapter, { ...state, status:freshStatus });\n      if (TERMINAL_STATES.has(job.status)) return;\n      if (job.productionPaused === true) {\n        this.resetAutomaticAssignment(job);\n        await this.persistAndNotify();\n        return;\n      }\n\n      job.status = 'preflight';\n"""
if old not in text: raise SystemExit('post-upload pause anchor not found')
text = text.replace(old, new, 1)

old = """      job.toolSnapshot = adapter.capabilities?.printToolMapping ? buildToolSnapshot({ status:finalStatus }, job.options.toolMap) : [];\n      if (this.chamberPreheat.isActive(printer.id)) {\n        await this.chamberPreheat.stop(printer.id, { reason:'queued-print-started', turnOff:false });\n      }\n      if (TERMINAL_STATES.has(job.status)) return;\n      job.status = 'starting';\n"""
new = """      job.toolSnapshot = adapter.capabilities?.printToolMapping ? buildToolSnapshot({ status:finalStatus }, job.options.toolMap) : [];\n      if (job.productionPaused === true) {\n        this.resetAutomaticAssignment(job);\n        await this.persistAndNotify();\n        return;\n      }\n      if (this.chamberPreheat.isActive(printer.id)) {\n        await this.chamberPreheat.stop(printer.id, { reason:'queued-print-started', turnOff:false });\n      }\n      if (TERMINAL_STATES.has(job.status)) return;\n      if (job.productionPaused === true) {\n        this.resetAutomaticAssignment(job);\n        await this.persistAndNotify();\n        return;\n      }\n      job.status = 'starting';\n"""
if old not in text: raise SystemExit('pre-start pause anchor not found')
text = text.replace(old, new, 1)
queue_path.write_text(text)

app_path = Path('print-farm-controller/public/app.js')
text = app_path.read_text()
old = """  const remaining = Number(batch.remaining || 0);\n  const failed = Number(batch.failed || 0);\n"""
new = """  const remaining = Number(batch.remaining || 0);\n  const cancelable = Number(batch.cancelable || remaining);\n  const failed = Number(batch.failed || 0);\n"""
if old not in text: raise SystemExit('UI cancelable variable anchor not found')
text = text.replace(old, new, 1)
old = """      ${remaining ? `<button type=\"button\" class=\"danger\" data-production-action=\"cancel\" data-production-batch=\"${escapeHtml(batch.id)}\">Cancel remaining</button>` : ''}\n"""
new = """      ${cancelable ? `<button type=\"button\" class=\"danger\" data-production-action=\"cancel\" data-production-batch=\"${escapeHtml(batch.id)}\">Cancel remaining</button>` : ''}\n"""
if old not in text: raise SystemExit('UI cancel remaining anchor not found')
text = text.replace(old, new, 1)
app_path.write_text(text)

# Add race regression tests.
tests_path = Path('print-farm-controller/test/print-queue.test.js')
text = tests_path.read_text()
block = r'''

test('pausing a production batch during staged upload prevents that copy from starting until resumed', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', name:'Printer', online:true, status:{ status:'idle', fileName:null, tools:[{ index:0, filament:{} }] } }]);
  const store = memoryStore();
  const staged = {
    id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', fileName:'paused-batch.gcode', filePath:'/staged/paused-batch.gcode', size:10, sha256:'f'.repeat(64), stagedAt:new Date().toISOString(),
    requirements:{ requiredTools:[0], toolCount:1, usageReliable:true, logicalTools:[{ index:0 }], materialMetadata:{ metadataAvailable:false, materials:[] } }
  };
  let releaseUpload;
  const uploadGate = new Promise((resolve) => { releaseUpload = resolve; });
  let uploaded = false;
  let starts = 0;
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn:async () => ({ id:'p1', name:'Printer' }),
    adapterResolver:() => ({
      capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true }, limits:{ toolCount:1 }, uploadExtensions:['.gcode'],
      getStatus:async () => fleetState.getPrinterState('p1').status,
      verifyFile:async () => ({ verified:uploaded, source:'test' }),
      uploadFile:async () => { await uploadGate; uploaded = true; },
      printLocalFile:async () => { starts++; }
    }),
    loadJobsFn:store.load,
    saveJobsFn:store.save,
    getQueueFileFn:async () => staged,
    pruneQueueFilesFn:async () => 0,
    saveFileMaterialMetadataFn:async () => {}
  });
  await service.start();
  const first = await service.add({ assignmentMode:'automatic', stagedFileId:staged.id, quantity:2 });
  await waitFor(() => service.getProductionJobs(first.productionBatchId).some((job) => job.status === 'uploading'));
  await service.pauseProduction(first.productionBatchId);
  releaseUpload();
  await waitFor(() => service.getProductionJobs(first.productionBatchId).every((job) => job.status === 'queued'));
  assert.equal(starts, 0);
  assert.equal(service.getSnapshot().productionBatches[0].paused, true);
  await service.resumeProduction(first.productionBatchId);
  await waitFor(() => starts === 1);
  service.stop();
});

test('cancel remaining catches a production copy already uploading without cancelling active prints', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', name:'Printer', online:true, status:{ status:'idle', fileName:null, tools:[{ index:0, filament:{} }] } }]);
  const store = memoryStore();
  const staged = {
    id:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', fileName:'cancel-batch.gcode', filePath:'/staged/cancel-batch.gcode', size:10, sha256:'1'.repeat(64), stagedAt:new Date().toISOString(),
    requirements:{ requiredTools:[0], toolCount:1, usageReliable:true, logicalTools:[{ index:0 }], materialMetadata:{ metadataAvailable:false, materials:[] } }
  };
  let releaseUpload;
  const uploadGate = new Promise((resolve) => { releaseUpload = resolve; });
  let starts = 0;
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn:async () => ({ id:'p1', name:'Printer' }),
    adapterResolver:() => ({
      capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true }, limits:{ toolCount:1 }, uploadExtensions:['.gcode'],
      getStatus:async () => fleetState.getPrinterState('p1').status,
      verifyFile:async () => ({ verified:false, source:'test' }),
      uploadFile:async () => { await uploadGate; },
      printLocalFile:async () => { starts++; }
    }),
    loadJobsFn:store.load,
    saveJobsFn:store.save,
    getQueueFileFn:async () => staged,
    pruneQueueFilesFn:async () => 0,
    saveFileMaterialMetadataFn:async () => {}
  });
  await service.start();
  const first = await service.add({ assignmentMode:'automatic', stagedFileId:staged.id, quantity:2 });
  await waitFor(() => service.getProductionJobs(first.productionBatchId).some((job) => job.status === 'uploading'));
  const result = await service.cancelProduction(first.productionBatchId);
  assert.equal(result.cancelled, 2);
  releaseUpload();
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(starts, 0);
  assert.ok(service.getProductionJobs(first.productionBatchId).every((job) => job.status === 'cancelled'));
  service.stop();
});
'''
if "pausing a production batch during staged upload prevents" not in text:
    tests_path.write_text(text + block)
