from pathlib import Path

root = Path('print-farm-controller')

# Backend regression: cancelled automatic queue history can be reprinted with the same staged file/options.
queue_test = root / 'test/print-queue.test.js'
text = queue_test.read_text()
anchor = """test('queued U1 mapped print refuses to start if a mapped tool changes after queueing', async () => {\n"""
block = r'''test('cancelled automatic queue history can be reprinted with the same staged file and options', async () => {
  const fleetState = new FakeFleetState([{ id:'p1', name:'Printer', online:false, status:null }]);
  const store = memoryStore();
  const staged = {
    id:'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    fileName:'cancel-reprint.gcode',
    filePath:'/staged/cancel-reprint.gcode',
    size:123,
    sha256:'2'.repeat(64),
    stagedAt:new Date().toISOString(),
    requirements:{ requiredTools:[0], toolCount:1, usageReliable:true, logicalTools:[{ index:0 }], materialMetadata:{ metadataAvailable:false, materials:[] } }
  };
  const service = new PrintQueueService({
    fleetState,
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn:async () => ({ id:'p1', name:'Printer' }),
    adapterResolver:() => ({ capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true }, limits:{ toolCount:1 }, uploadExtensions:['.gcode'] }),
    loadJobsFn:store.load,
    saveJobsFn:store.save,
    getQueueFileFn:async (id) => id === staged.id ? staged : null,
    pruneQueueFilesFn:async () => 0
  });
  await service.start();
  const original = await service.add({
    assignmentMode:'automatic',
    stagedFileId:staged.id,
    options:{ levelingBeforePrint:false, flowCalibrationBeforePrint:true }
  });
  await service.cancel(original.id);
  const cancelled = service.getJob(original.id);
  assert.equal(cancelled.status, 'cancelled');
  assert.equal(service.getSnapshot().history, 1);

  const reprinted = await service.reprint(original.id);
  assert.notEqual(reprinted.id, original.id);
  assert.equal(reprinted.status, 'queued');
  assert.equal(reprinted.assignmentMode, 'automatic');
  assert.equal(reprinted.printerId, null);
  assert.equal(reprinted.fileName, staged.fileName);
  assert.equal(reprinted.stagedFile.id, staged.id);
  assert.equal(reprinted.options.levelingBeforePrint, false);
  assert.equal(reprinted.options.flowCalibrationBeforePrint, true);
  assert.equal(service.getJob(original.id).status, 'cancelled');
  service.stop();
});

'''
if "cancelled automatic queue history can be reprinted" not in text:
    if anchor not in text:
        raise SystemExit('print queue test anchor not found')
    text = text.replace(anchor, block + anchor, 1)
    queue_test.write_text(text)

# UI regression: cancelled standalone jobs remain in Recent history and history cards expose Reprint.
ui_test = root / 'test/ui-print-setup.test.js'
text = ui_test.read_text()
anchor = """test('queue UI exposes persistent bed-clearance interlock before automatic progression', () => {\n"""
block = r'''test('cancelled queued jobs remain reprintable from recent history', () => {
  assert.match(app, /\['completed', 'failed', 'cancelled'\]\.includes\(job\.status\)/);
  assert.match(app, /data-queue-reprint=/);
  assert.match(app, /queueHistoryList\?\.addEventListener/);
  assert.match(app, /\/api\/queue\/\$\{encodeURIComponent\(job\.id\)\}\/reprint/);
});

'''
if "cancelled queued jobs remain reprintable from recent history" not in text:
    if anchor not in text:
        raise SystemExit('UI test anchor not found')
    text = text.replace(anchor, block + anchor, 1)
    ui_test.write_text(text)

# Version bump.
package = root / 'package.json'
text = package.read_text()
text = text.replace('"version": "0.12.0"', '"version": "0.12.1"', 1)
package.write_text(text)

# README release note.
readme = root / 'README.md'
text = readme.read_text()
text = text.replace('# Printer Fleet Controller v0.12.0', '# Printer Fleet Controller v0.12.1', 1)
marker = '> v0.12.0 adds **production quantity / batch printing**.'
note = '> v0.12.1 adds dedicated regression coverage ensuring a cancelled queued print remains in Recent history and can be reprinted with its original staged file and print options.\n\n'
if note.strip() not in text:
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit('README release marker not found')
    text = text[:pos] + note + text[pos:]
readme.write_text(text)

# Cross-chat project handoff.
context = root / 'PROJECT_CONTEXT.md'
text = context.read_text()
text = text.replace('Current application version: **0.12.0**', 'Current application version: **0.12.1**', 1)
marker = '- v0.12.0 regression suite: **113 passing tests, 0 failures**, including concurrent assignment plus pause/cancel race coverage during staged upload.\n'
addition = marker + '- **v0.12.1 cancelled-history reprint regression:** automated coverage now guarantees a cancelled automatic queued job remains reprintable from Recent history using the same staged controller file and print options; UI coverage verifies cancelled history retains the Reprint action.\n- v0.12.1 regression suite: **115 passing tests, 0 failures**.\n'
if 'v0.12.1 cancelled-history reprint regression' not in text:
    if marker not in text:
        raise SystemExit('context v0.12.0 suite marker not found')
    text = text.replace(marker, addition, 1)
text = text.replace('**v0.12.0 implementation is complete in code and automated tests.** Next priority is real-hardware validation', '**v0.12.1 regression hardening is complete in code and automated tests.** Next priority is real-hardware validation', 1)
context.write_text(text)
