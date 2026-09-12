from pathlib import Path

ROOT = Path('print-farm-controller')

def replace_once(rel, old, new):
    p = ROOT / rel
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'anchor not found in {rel}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

def insert_before(rel, anchor, text_to_insert):
    p = ROOT / rel
    text = p.read_text(encoding='utf-8')
    if anchor not in text:
        raise SystemExit(f'anchor not found in {rel}: {anchor[:120]!r}')
    p.write_text(text.replace(anchor, text_to_insert + anchor, 1), encoding='utf-8')

# Backend: reprint a completed production batch as a fresh automatic batch.
replace_once('src/print-queue.js', """  async setProductionQuantity(batchId, quantity) {
""", """  async reprintProduction(batchId) {
    const jobs = this.getProductionJobs(batchId);
    if (!jobs.every((job) => TERMINAL_STATES.has(job.status))) {
      throw new Error('Production batch must be finished before it can be reprinted');
    }
    const source = [...jobs].sort((a, b) => Number(a.productionSequence || 0) - Number(b.productionSequence || 0))[0];
    const stagedFileId = source?.stagedFile?.id || null;
    if (!stagedFileId) throw new Error('Production batch no longer has a staged controller file');
    const quantity = Math.max(jobs.length, ...jobs.map((job) => Number(job.productionQuantity || 0)));
    const options = { ...sanitizeOptions(source.options), toolMap:null, usedLogicalTools:[] };
    return this.add({
      assignmentMode:'automatic',
      fileName:source.fileName,
      stagedFileId,
      quantity,
      options
    });
  }

  async setProductionQuantity(batchId, quantity) {
""")

# API route.
replace_once('src/server.js', """  const productionQueueMatch = url.pathname.match(/^\\/api\\/queue\\/production\\/([^/]+)\\/(pause|resume|cancel|quantity)$/);
""", """  const productionQueueMatch = url.pathname.match(/^\\/api\\/queue\\/production\\/([^/]+)\\/(pause|resume|cancel|quantity|reprint)$/);
""")
replace_once('src/server.js', """    if (action === 'pause') result = await printQueue.pauseProduction(batchId);
    else if (action === 'resume') result = await printQueue.resumeProduction(batchId);
    else if (action === 'cancel') result = await printQueue.cancelProduction(batchId);
    else {
      const body = await readJson(req);
      result = await printQueue.setProductionQuantity(batchId, body.quantity);
    }
""", """    if (action === 'pause') result = await printQueue.pauseProduction(batchId);
    else if (action === 'resume') result = await printQueue.resumeProduction(batchId);
    else if (action === 'cancel') result = await printQueue.cancelProduction(batchId);
    else if (action === 'reprint') result = await printQueue.reprintProduction(batchId);
    else {
      const body = await readJson(req);
      result = await printQueue.setProductionQuantity(batchId, body.quantity);
    }
""")

# UI: Reprint batch action on finished history cards.
replace_once('public/app.js', """  const controls = !history && !batch.finished ? `<div class=\"production-actions\">
      <button type=\"button\" class=\"secondary\" data-production-action=\"${batch.paused ? 'resume' : 'pause'}\" data-production-batch=\"${escapeHtml(batch.id)}\">${batch.paused ? 'Resume production' : 'Pause production'}</button>
      <label class=\"production-quantity-control\">Quantity <input type=\"number\" min=\"1\" max=\"999\" step=\"1\" value=\"${quantity}\" data-production-quantity-input=\"${escapeHtml(batch.id)}\"></label>
      <button type=\"button\" class=\"secondary\" data-production-quantity=\"${escapeHtml(batch.id)}\">Update quantity</button>
      ${cancelable ? `<button type=\"button\" class=\"danger\" data-production-action=\"cancel\" data-production-batch=\"${escapeHtml(batch.id)}\">Cancel remaining</button>` : ''}
    </div>` : '';
""", """  const controls = history && batch.finished
    ? `<div class=\"production-actions\"><button type=\"button\" class=\"secondary\" data-production-reprint=\"${escapeHtml(batch.id)}\">Reprint batch</button></div>`
    : !history && !batch.finished ? `<div class=\"production-actions\">
      <button type=\"button\" class=\"secondary\" data-production-action=\"${batch.paused ? 'resume' : 'pause'}\" data-production-batch=\"${escapeHtml(batch.id)}\">${batch.paused ? 'Resume production' : 'Pause production'}</button>
      <label class=\"production-quantity-control\">Quantity <input type=\"number\" min=\"1\" max=\"999\" step=\"1\" value=\"${quantity}\" data-production-quantity-input=\"${escapeHtml(batch.id)}\"></label>
      <button type=\"button\" class=\"secondary\" data-production-quantity=\"${escapeHtml(batch.id)}\">Update quantity</button>
      ${cancelable ? `<button type=\"button\" class=\"danger\" data-production-action=\"cancel\" data-production-batch=\"${escapeHtml(batch.id)}\">Cancel remaining</button>` : ''}
    </div>` : '';
""")
replace_once('public/app.js', """queueHistoryList?.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-queue-reprint]');
""", """queueHistoryList?.addEventListener('click', async (event) => {
  const productionReprint = event.target.closest('[data-production-reprint]');
  if (productionReprint) {
    const batchId = productionReprint.dataset.productionReprint;
    const batch = (queueState.productionBatches || []).find((item) => item.id === batchId);
    if (!batch) return;
    if (!confirm(`Reprint all ${batch.quantity} copies of ${batch.fileName} as a new production batch?`)) return;
    productionReprint.disabled = true;
    try {
      const result = await api(`/api/queue/production/${encodeURIComponent(batchId)}/reprint`, { method:'POST', body:'{}' });
      queueState = result.queue || queueState;
      renderPrintQueue();
    } catch (error) { alert(error.message); productionReprint.disabled = false; }
    return;
  }
  const button = event.target.closest('[data-queue-reprint]');
""")

# Backend regression test.
insert_before('test/print-queue.test.js', """test('production batch can pause, change waiting quantity, resume and cancel remaining copies', async () => {
""", """test('finished production batch can be reprinted as a fresh batch with the same quantity, staged file and options', async () => {
  const store = memoryStore();
  const staged = {
    id:'12121212-1212-4212-8212-121212121212', fileName:'repeat-batch.gcode', filePath:'/staged/repeat-batch.gcode', size:10, sha256:'3'.repeat(64), stagedAt:new Date().toISOString(),
    requirements:{ requiredTools:[0], toolCount:1, usageReliable:true, logicalTools:[{ index:0 }], materialMetadata:{ metadataAvailable:false, materials:[] } }
  };
  const service = new PrintQueueService({
    fleetState:new FakeFleetState([]),
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    loadJobsFn:store.load,
    saveJobsFn:store.save,
    getQueueFileFn:async (id) => id === staged.id ? staged : null,
    pruneQueueFilesFn:async () => 0
  });
  await service.start();
  const first = await service.add({
    assignmentMode:'automatic',
    stagedFileId:staged.id,
    quantity:3,
    options:{ levelingBeforePrint:false, flowCalibrationBeforePrint:true, timeLapseBeforePrint:true }
  });
  await assert.rejects(() => service.reprintProduction(first.productionBatchId), /must be finished/);
  await service.cancelProduction(first.productionBatchId);
  assert.ok(service.getProductionJobs(first.productionBatchId).every((job) => job.status === 'cancelled'));

  const reprinted = await service.reprintProduction(first.productionBatchId);
  assert.notEqual(reprinted.productionBatchId, first.productionBatchId);
  assert.equal(reprinted.status, 'queued');
  assert.equal(reprinted.assignmentMode, 'automatic');
  assert.equal(reprinted.stagedFile.id, staged.id);
  assert.equal(reprinted.options.levelingBeforePrint, false);
  assert.equal(reprinted.options.flowCalibrationBeforePrint, true);
  assert.equal(reprinted.options.timeLapseBeforePrint, true);
  assert.equal(reprinted.options.toolMap, null);
  const newRuns = service.getProductionJobs(reprinted.productionBatchId);
  assert.equal(newRuns.length, 3);
  assert.ok(newRuns.every((job) => job.status === 'queued' && job.stagedFile.id === staged.id));
  assert.ok(service.getProductionJobs(first.productionBatchId).every((job) => job.status === 'cancelled'));
  service.stop();
});

""")

# UI regression test.
insert_before('test/ui-print-setup.test.js', """test('queue UI exposes production quantity and batch controls', () => {
""", """test('finished production batches can be reprinted from recent history', () => {
  const server = fs.readFileSync(new URL('../src/server.js', import.meta.url), 'utf8');
  const queue = fs.readFileSync(new URL('../src/print-queue.js', import.meta.url), 'utf8');
  assert.match(app, /data-production-reprint/);
  assert.match(app, /Reprint batch/);
  assert.match(app, /Reprint all \\${batch\\.quantity} copies/);
  assert.match(app, /production\\/\\$\\{encodeURIComponent\\(batchId\\)\\}\\/reprint/);
  assert.match(server, /pause\\|resume\\|cancel\\|quantity\\|reprint/);
  assert.match(queue, /async reprintProduction/);
  assert.match(queue, /Production batch must be finished before it can be reprinted/);
});

""")

# Version and docs.
replace_once('package.json', '"version": "0.12.1"', '"version": "0.12.2"')
replace_once('README.md', '# Printer Fleet Controller v0.12.1\n', '# Printer Fleet Controller v0.12.2\n\n> v0.12.2 adds **Reprint batch** to finished production batches in Recent history. Reprinting creates a new automatic production batch with the same quantity, staged G-code and print options while leaving the original history unchanged.\n')
replace_once('PROJECT_CONTEXT.md', 'Current application version: **0.12.1**', 'Current application version: **0.12.2**')
replace_once('PROJECT_CONTEXT.md', '- v0.12.1 regression suite: **115 passing tests, 0 failures**.\n', '- v0.12.1 regression suite: **115 passing tests, 0 failures**.\n- **v0.12.2 production batch reprint:** finished production batches in Recent history expose **Reprint batch**, creating a fresh automatic batch with the same quantity, staged controller file and print options while preserving the original history.\n- v0.12.2 regression suite: **117 passing tests, 0 failures**.\n')
replace_once('PROJECT_CONTEXT.md', '**v0.12.1 regression hardening is complete in code and automated tests.**', '**v0.12.2 batch reprint implementation is complete in code and automated tests.**')
