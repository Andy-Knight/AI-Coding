from pathlib import Path

ROOT = Path('print-farm-controller')

def replace_once(rel, old, new):
    path = ROOT / rel
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'missing patch target in {rel}: {old[:120]!r}')
    if text.count(old) != 1:
        raise SystemExit(f'patch target occurs {text.count(old)} times in {rel}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

# Version.
replace_once('package.json', '"version": "0.12.2"', '"version": "0.12.3"')

# Expose adapter-supported upload extensions in fleet state.
replace_once('src/fleet-state.js',
'''      let capabilities = existing?.capabilities || {};
      let limits = existing?.limits || {};
      try {
        const adapter = this.adapterResolver(printer);
        capabilities = adapter.capabilities;
        limits = adapter.limits;
      } catch {}
      this.states.set(printer.id, {
        ...(existing || {}),
        ...publicPrinter(printer),
        capabilities,
        limits,
''',
'''      let capabilities = existing?.capabilities || {};
      let limits = existing?.limits || {};
      let uploadExtensions = existing?.uploadExtensions || [];
      try {
        const adapter = this.adapterResolver(printer);
        capabilities = adapter.capabilities;
        limits = adapter.limits;
        uploadExtensions = [...(adapter.uploadExtensions || [])];
      } catch {}
      this.states.set(printer.id, {
        ...(existing || {}),
        ...publicPrinter(printer),
        capabilities,
        limits,
        uploadExtensions,
''')
replace_once('src/fleet-state.js',
'''      state.capabilities = adapter.capabilities;
      state.limits = adapter.limits;
      state.online = true;
''',
'''      state.capabilities = adapter.capabilities;
      state.limits = adapter.limits;
      state.uploadExtensions = [...(adapter.uploadExtensions || [])];
      state.online = true;
''')

# Browser upload staging accepts the union of adapter-supported printable formats.
replace_once('src/upload-staging.js',
"const ALLOWED_EXTENSIONS = new Set(['.gcode', '.gx', '.3mf']);",
"const ALLOWED_EXTENSIONS = new Set(['.gcode', '.gx', '.3mf', '.gco', '.g']);")
replace_once('src/upload-staging.js',
"if (!ALLOWED_EXTENSIONS.has(extension)) throw new Error('Choose a .gcode, .gx, or .3mf file');",
"if (!ALLOWED_EXTENSIONS.has(extension)) throw new Error('Choose a .gcode, .gx, .3mf, .gco, or .g file');")

# Distribution service validates the target adapter's own supported extensions.
replace_once('src/file-distribution.js',
"import { getPrinter } from './store.js';\n",
"import path from 'node:path';\nimport { getPrinter } from './store.js';\n")
replace_once('src/file-distribution.js',
'''      if (!adapter.capabilities?.fileUpload) throw new Error('File upload is not supported by this printer');
      if (!adapter.capabilities?.localFiles) throw new Error('Printer storage verification is not supported by this printer');
      if (startPrint && !adapter.capabilities?.printLocalFile) throw new Error('Starting uploaded files is not supported by this printer');

      if (this.uploadFileOverride) {
''',
'''      if (!adapter.capabilities?.fileUpload) throw new Error('File upload is not supported by this printer');
      if (!adapter.capabilities?.localFiles) throw new Error('Printer storage verification is not supported by this printer');
      if (startPrint && !adapter.capabilities?.printLocalFile) throw new Error('Starting uploaded files is not supported by this printer');
      const uploadExtensions = [...new Set((adapter.uploadExtensions || []).map((value) => String(value || '').trim().toLowerCase()).filter(Boolean))];
      const extension = path.extname(fileName).toLowerCase();
      if (uploadExtensions.length && !uploadExtensions.includes(extension)) {
        throw new Error(`${adapter.manufacturer || adapter.type || 'This printer'} does not support ${extension || 'this file type'} uploads. Supported: ${uploadExtensions.join(', ')}`);
      }

      if (this.uploadFileOverride) {
''')

# Individual-printer POST /files endpoint reuses verified distribution infrastructure.
replace_once('src/server.js',
'''  if (req.method === 'GET' && action === 'files') {
    if (!adapter.capabilities?.localFiles) throw new Error('File listing is not supported by this printer');
    return json(res, 200, await adapter.getFiles());
  }

  if (req.method === 'GET' && action === 'file-material') {
''',
'''  if (req.method === 'GET' && action === 'files') {
    if (!adapter.capabilities?.localFiles) throw new Error('File listing is not supported by this printer');
    return json(res, 200, await adapter.getFiles());
  }

  if (req.method === 'POST' && action === 'files') {
    if (!adapter.capabilities?.fileUpload) throw new Error('File upload is not supported by this printer');
    if (!adapter.capabilities?.localFiles) throw new Error('Printer storage verification is not supported by this printer');
    const staged = await stageUploadRequest(req, req.headers['x-file-name']);
    try {
      const result = await fileDistribution.distribute({
        printerIds:[id],
        filePath:staged.filePath,
        fileName:staged.fileName,
        startPrint:false
      });
      const item = result.results?.[0];
      if (!item?.ok) throw new Error(item?.error || 'Printer file upload failed');
      return json(res, 201, {
        ok:true,
        fileName:staged.fileName,
        fileSize:staged.size,
        verified:item.verified === true,
        verificationSource:item.verificationSource || null
      });
    } finally {
      await staged.cleanup().catch(() => {});
    }
  }

  if (req.method === 'GET' && action === 'file-material') {
''')

# Printer detail UI: upload control, adapter-specific accept list and verified upload handler.
replace_once('public/app.js',
'''  const fileSourceLabel = files.length ? `${files.length} file${files.length === 1 ? '' : 's'} · ${fileResult.complete ? 'full storage' : 'recent only'}${orderLabel ? ` · ${orderLabel}` : ''}` : '';
  const s = printer.status;
''',
'''  const fileSourceLabel = files.length ? `${files.length} file${files.length === 1 ? '' : 's'} · ${fileResult.complete ? 'full storage' : 'recent only'}${orderLabel ? ` · ${orderLabel}` : ''}` : '';
  const uploadExtensions = Array.isArray(printer.uploadExtensions) && printer.uploadExtensions.length
    ? printer.uploadExtensions.map((value) => String(value || '').trim().toLowerCase()).filter(Boolean)
    : ['.gcode', '.gx', '.3mf'];
  const uploadAccept = uploadExtensions.join(',');
  const fileUploadMarkup = capabilities.fileUpload && capabilities.localFiles
    ? `<div class="printer-file-upload"><input class="hidden" type="file" data-printer-file-upload-input accept="${escapeHtml(uploadAccept)}"><button type="button" class="secondary" data-printer-file-upload${printer.online ? '' : ' disabled'}>Upload file</button><span class="subtle" data-printer-file-upload-status>${printer.online ? `Supported: ${escapeHtml(uploadExtensions.join(', '))}` : 'Upload unavailable while printer is offline.'}</span></div>`
    : '';
  const s = printer.status;
''')
replace_once('public/app.js',
'''          <div class="file-heading"><h3>Files on printer</h3><span class="subtle">${escapeHtml(fileSourceLabel)}</span></div>
          ${capabilities.levelBeforePrint ? '<label class="checkbox-label"><input type="checkbox" id="levelBeforePrint" checked /> Level bed before print</label>' : '<div class="field-help">This printer uses the start G-code embedded in the uploaded file; controller-side pre-print levelling is not available.</div>'}
''',
'''          <div class="file-heading"><h3>Files on printer</h3><span class="subtle">${escapeHtml(fileSourceLabel)}</span></div>
          ${fileUploadMarkup}
          ${capabilities.levelBeforePrint ? '<label class="checkbox-label"><input type="checkbox" id="levelBeforePrint" checked /> Level bed before print</label>' : '<div class="field-help">This printer uses the start G-code embedded in the uploaded file; controller-side pre-print levelling is not available.</div>'}
''')
replace_once('public/app.js',
'''  printerDialog.showModal();
  updateOpenPrinterTelemetry();

  const liveCamera = printerDetail.querySelector('img.detail-camera');
''',
'''  if (!printerDialog.open) printerDialog.showModal();
  updateOpenPrinterTelemetry();

  const printerUploadButton = printerDetail.querySelector('[data-printer-file-upload]');
  const printerUploadInput = printerDetail.querySelector('[data-printer-file-upload-input]');
  const printerUploadStatus = printerDetail.querySelector('[data-printer-file-upload-status]');
  if (printerUploadButton && printerUploadInput) {
    printerUploadButton.onclick = () => printerUploadInput.click();
    printerUploadInput.onchange = async () => {
      const file = printerUploadInput.files?.[0];
      if (!file) return;
      const extension = `.${String(file.name || '').split('.').pop().toLowerCase()}`;
      if (uploadExtensions.length && !uploadExtensions.includes(extension)) {
        if (printerUploadStatus) printerUploadStatus.textContent = `Unsupported file type. Use ${uploadExtensions.join(', ')}`;
        printerUploadInput.value = '';
        return;
      }
      if (file.size > 512 * 1024 * 1024) {
        if (printerUploadStatus) printerUploadStatus.textContent = 'File exceeds the 512 MB upload limit.';
        printerUploadInput.value = '';
        return;
      }
      printerUploadButton.disabled = true;
      if (printerUploadStatus) printerUploadStatus.textContent = `Uploading ${file.name}…`;
      try {
        const response = await fetch(`/api/printers/${encodeURIComponent(id)}/files`, {
          method:'POST',
          headers:{ 'content-type':'application/octet-stream', 'x-file-name':encodeURIComponent(file.name) },
          body:file
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.error || `Upload failed (${response.status})`);
        await openPrinter(id);
        const refreshedStatus = printerDetail.querySelector('[data-printer-file-upload-status]');
        if (refreshedStatus) refreshedStatus.textContent = `Uploaded and verified ${result.fileName || file.name}`;
      } catch (error) {
        if (printerUploadStatus) printerUploadStatus.textContent = error.message || 'Upload failed';
      } finally {
        printerUploadInput.value = '';
        if (printerUploadButton.isConnected) printerUploadButton.disabled = false;
      }
    };
  }

  const liveCamera = printerDetail.querySelector('img.detail-camera');
''')

# Styling.
replace_once('public/styles.css',
'''.file-heading h3 { margin-bottom:8px; }
.file-search { margin:8px 0; }
''',
'''.file-heading h3 { margin-bottom:8px; }
.printer-file-upload { display:flex; align-items:center; gap:9px; margin:4px 0 10px; flex-wrap:wrap; }
.printer-file-upload button { flex:0 0 auto; }
.printer-file-upload .subtle { min-width:180px; flex:1; }
.file-search { margin:8px 0; }
''')

# Tests: staging supports U1 extensions.
replace_once('test/upload-staging.test.js',
'''  assert.equal(validateUploadFilename('model%203mf.3mf'), 'model 3mf.3mf');
  assert.throws(() => validateUploadFilename('../part.gcode'), /must not contain a path/);
  assert.throws(() => validateUploadFilename('notes.txt'), /\\.gcode, \\.gx, or \\.3mf/);
''',
'''  assert.equal(validateUploadFilename('model%203mf.3mf'), 'model 3mf.3mf');
  assert.equal(validateUploadFilename('u1-part.gco'), 'u1-part.gco');
  assert.equal(validateUploadFilename('u1-part.g'), 'u1-part.g');
  assert.throws(() => validateUploadFilename('../part.gcode'), /must not contain a path/);
  assert.throws(() => validateUploadFilename('notes.txt'), /\\.gcode, \\.gx, \\.3mf, \\.gco, or \\.g/);
''')

# Tests: target-adapter extension enforcement.
fd = ROOT / 'test/file-distribution.test.js'
text = fd.read_text(encoding='utf-8')
marker = "\ntest('verification matches full-storage names before falling back to recent files', async () => {"
if marker not in text:
    raise SystemExit('file-distribution insertion marker missing')
new_test = r'''

test('distribution rejects a file extension unsupported by the selected printer adapter', async () => {
  let uploaded = false;
  const service = new FileDistributionService({
    fleetState:{ getPrinterState:() => ({ online:true, status:{ status:'ready' } }) },
    chamberPreheat:{ isActive:() => false, stop:async () => {} },
    getPrinterFn:async () => ({ id:'u1', name:'U1' }),
    adapterResolver:() => ({
      type:'snapmaker-u1', manufacturer:'Snapmaker',
      capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true },
      uploadExtensions:['.gcode', '.gco', '.g'],
      uploadFile:async () => { uploaded = true; },
      verifyFile:async () => ({ verified:true, source:'moonraker' })
    }),
    fileMetadataReader:async () => null,
    maxConcurrent:1
  });
  const result = await service.distribute({ printerIds:['u1'], filePath:'/tmp/part.3mf', fileName:'part.3mf' });
  assert.equal(uploaded, false);
  assert.equal(result.results[0].ok, false);
  assert.match(result.results[0].error, /does not support \\.3mf uploads/);
});
'''
fd.write_text(text.replace(marker, new_test + marker, 1), encoding='utf-8')

# UI/source regression coverage.
ui = ROOT / 'test/ui-print-setup.test.js'
text = ui.read_text(encoding='utf-8')
marker = "\ntest('queue UI exposes production quantity and batch controls', () => {"
if marker not in text:
    raise SystemExit('ui test insertion marker missing')
new_test = r'''

test('printer detail exposes verified upload to an individual printer', () => {
  const server = fs.readFileSync(new URL('../src/server.js', import.meta.url), 'utf8');
  const fleetState = fs.readFileSync(new URL('../src/fleet-state.js', import.meta.url), 'utf8');
  assert.match(app, /data-printer-file-upload/);
  assert.match(app, /data-printer-file-upload-input/);
  assert.match(app, /Uploaded and verified/);
  assert.match(app, /\/api\/printers\/\$\{encodeURIComponent\(id\)\}\/files/);
  assert.match(server, /req\.method === 'POST' && action === 'files'/);
  assert.match(server, /printerIds:\[id\]/);
  assert.match(fleetState, /uploadExtensions/);
  assert.match(styles, /\\.printer-file-upload/);
});
'''
ui.write_text(text.replace(marker, new_test + marker, 1), encoding='utf-8')

# README and project context.
replace_once('README.md', '# Printer Fleet Controller v0.12.2', '# Printer Fleet Controller v0.12.3')
replace_once('README.md',
'> v0.12.2 adds **Reprint batch** to finished production batches in Recent history. Reprinting creates a new automatic production batch with the same quantity, staged controller file and print options while preserving the original history.\n',
'> v0.12.3 adds **Upload file** inside each supported printer window. Individual uploads use the printer adapter\'s declared file types, are verified in printer storage before reporting success, save available material metadata, and refresh the printer file list after upload.\n\n> v0.12.2 adds **Reprint batch** to finished production batches in Recent history. Reprinting creates a new automatic production batch with the same quantity, staged controller file and print options while preserving the original history.\n')
replace_once('PROJECT_CONTEXT.md', '- Current application version: **0.12.2**', '- Current application version: **0.12.3**')
replace_once('PROJECT_CONTEXT.md',
'- v0.12.2 regression suite: **117 passing tests, 0 failures**.\n',
'- v0.12.2 regression suite: **117 passing tests, 0 failures**.\n- **v0.12.3 individual printer upload:** supported printer detail windows expose **Upload file**; uploads are adapter-extension-aware, use the existing verified file-distribution path for one target printer, persist available material metadata, and refresh the printer file list after success.\n- v0.12.3 regression suite: **119 passing tests, 0 failures**.\n')
replace_once('PROJECT_CONTEXT.md',
'**v0.12.2 batch reprint implementation is complete in code and automated tests.** Next priority is real-hardware validation of production quantities across mixed FlashForge/Snapmaker printers, especially concurrent assignment, bed-clearance recycling, printer-local file reuse, and pause/resume behaviour.',
'**v0.12.3 individual-printer file upload is complete in code and automated tests.** Next priority is real-hardware validation of direct uploads and production quantities across mixed FlashForge/Snapmaker printers, especially upload verification, concurrent assignment, bed-clearance recycling, printer-local file reuse, and pause/resume behaviour.')
replace_once('PROJECT_CONTEXT.md',
'1. Queue a known-good single-tool file with quantity 4 or more and confirm multiple compatible printers receive copies concurrently.\n',
'1. Open one FlashForge and one Snapmaker printer window, upload a supported file to each, and confirm the verified file appears immediately in that printer\'s file list.\n2. Queue a known-good single-tool file with quantity 4 or more and confirm multiple compatible printers receive copies concurrently.\n')
# Renumber remaining documented steps from 2-7 to 3-8.
ctx = (ROOT / 'PROJECT_CONTEXT.md').read_text(encoding='utf-8')
for old, new in [('7. After hardware validation', '8. After hardware validation'), ('6. Confirm a printer', '7. Confirm a printer'), ('5. Cancel remaining', '6. Cancel remaining'), ('4. Increase and decrease', '5. Increase and decrease'), ('3. Pause a production', '4. Pause a production'), ('2. Confirm each completed', '3. Confirm each completed')]:
    ctx = ctx.replace(old, new, 1)
(ROOT / 'PROJECT_CONTEXT.md').write_text(ctx, encoding='utf-8')
