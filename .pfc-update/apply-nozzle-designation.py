from pathlib import Path

ROOT = Path('print-farm-controller')

def replace_once(rel, old, new):
    path = ROOT / rel
    text = path.read_text()
    if old not in text:
        raise SystemExit(f'needle not found in {rel}: {old[:120]!r}')
    if text.count(old) != 1:
        raise SystemExit(f'needle not unique in {rel}: {text.count(old)} matches')
    path.write_text(text.replace(old, new, 1))

replace_once('src/store.js',
"""function normalizeMaterialDesignation(value) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  if (text.length > 48) throw new Error('Material designation must be 48 characters or fewer');
  if (/[\x00-\x1f\x7f]/.test(text)) throw new Error('Material designation contains invalid characters');
  return text;
}

async function ensureStore() {""",
"""function normalizeMaterialDesignation(value) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  if (text.length > 48) throw new Error('Material designation must be 48 characters or fewer');
  if (/[\x00-\x1f\x7f]/.test(text)) throw new Error('Material designation contains invalid characters');
  return text;
}

function normalizeNozzleDesignation(value) {
  if (value == null || String(value).trim() === '') return null;
  const diameter = Number(value);
  if (!Number.isFinite(diameter) || diameter < 0.1 || diameter > 1.2) {
    throw new Error('Nozzle designation must be between 0.1 and 1.2 mm');
  }
  return Number(diameter.toFixed(3));
}

async function ensureStore() {""")
replace_once('src/store.js',
"""export async function reorderPrinters(printerIds) {""",
"""export async function setPrinterNozzleDesignation(id, nozzleDiameter) {
  const printers = await readAll();
  const index = printers.findIndex((printer) => printer.id === id);
  if (index < 0) return null;

  const designation = normalizeNozzleDesignation(nozzleDiameter);
  const adapterConfig = { ...(printers[index].adapterConfig || {}) };
  if (designation != null) adapterConfig.nozzleDiameterDesignation = designation;
  else delete adapterConfig.nozzleDiameterDesignation;

  printers[index] = { ...printers[index], adapterConfig };
  await writeAll(printers);
  return normalizeStoredPrinter(printers[index]);
}

export async function reorderPrinters(printerIds) {""")
replace_once('src/store.js',
"""    materialDesignation: String(printer.adapterConfig?.filamentDesignation || '').trim() || null,
    createdAt: printer.createdAt""",
"""    materialDesignation: String(printer.adapterConfig?.filamentDesignation || '').trim() || null,
    nozzleDiameterDesignation: Number.isFinite(Number(printer.adapterConfig?.nozzleDiameterDesignation))
      ? Number(printer.adapterConfig.nozzleDiameterDesignation)
      : null,
    createdAt: printer.createdAt""")

replace_once('src/adapters/printer-adapter.js',
"""  materialStatus: false,
  materialDesignation: false,
  printToolMapping: false,""",
"""  materialStatus: false,
  materialDesignation: false,
  nozzleDesignation: false,
  printToolMapping: false,""")
replace_once('src/adapters/flashforge-ad5m-adapter.js',
"""  chamberPreheat: true,
  materialStatus: true,
  materialDesignation: true
});""",
"""  chamberPreheat: true,
  materialStatus: true,
  materialDesignation: true,
  nozzleDesignation: true
});""")
replace_once('src/adapters/flashforge-ad5m-adapter.js',
"""      } else {
        filament.manuallyAssigned = false;
      }
    }
    return status;""",
"""      } else {
        filament.manuallyAssigned = false;
      }
    }

    const tool = status?.tools?.[0];
    if (tool) {
      const reportedNozzle = Number(tool.nozzleDiameter);
      const reportedNozzleDiameter = Number.isFinite(reportedNozzle) && reportedNozzle > 0 ? reportedNozzle : null;
      const manualNozzle = Number(this.printer.adapterConfig?.nozzleDiameterDesignation);
      const manualNozzleDiameter = Number.isFinite(manualNozzle) && manualNozzle > 0 ? manualNozzle : null;
      tool.reportedNozzleDiameter = reportedNozzleDiameter;
      if (manualNozzleDiameter) {
        tool.nozzleDiameter = manualNozzleDiameter;
        tool.nozzleDiameterSource = 'manual';
        tool.nozzleManuallyAssigned = true;
      } else {
        tool.nozzleDiameter = reportedNozzleDiameter;
        tool.nozzleDiameterSource = reportedNozzleDiameter ? 'printer' : null;
        tool.nozzleManuallyAssigned = false;
      }
    }
    return status;""")

replace_once('src/server.js',
"""  reorderPrinters,
  setPrinterMaterialDesignation
} from './store.js';""",
"""  reorderPrinters,
  setPrinterMaterialDesignation,
  setPrinterNozzleDesignation
} from './store.js';""")
replace_once('src/server.js',
"""  if (req.method === 'GET' && action === 'files') {""",
"""  if (action === 'nozzle-designation' && (req.method === 'POST' || req.method === 'DELETE')) {
    if (!adapter.capabilities?.nozzleDesignation) throw new Error('Manual nozzle designation is not supported by this printer');
    const body = req.method === 'POST' ? await readJson(req) : {};
    const updated = await setPrinterNozzleDesignation(id, req.method === 'POST' ? body.nozzleDiameter : null);
    if (!updated) throw new Error('Printer not found');
    await fleetState.syncRegistry();
    fleetState.refreshNow(id).catch(() => {});
    return json(res, 200, {
      ok: true,
      printer: publicPrinter(updated),
      nozzleDiameterDesignation: Number.isFinite(Number(updated.adapterConfig?.nozzleDiameterDesignation))
        ? Number(updated.adapterConfig.nozzleDiameterDesignation)
        : null
    });
  }

  if (req.method === 'GET' && action === 'files') {""")

replace_once('public/app.js',
"""  </div>`;
}

function nozzleDiameterText(value) {""",
"""  </div>`;
}

function flashForgeNozzleDesignationMarkup(printer, tool = {}) {
  if (!printer?.capabilities?.nozzleDesignation) return '';
  const manualValue = tool.nozzleDiameterSource === 'manual' && Number.isFinite(Number(tool.nozzleDiameter))
    ? Number(tool.nozzleDiameter)
    : (Number.isFinite(Number(printer.nozzleDiameterDesignation)) ? Number(printer.nozzleDiameterDesignation) : '');
  const reported = Number.isFinite(Number(tool.reportedNozzleDiameter)) && Number(tool.reportedNozzleDiameter) > 0
    ? Number(tool.reportedNozzleDiameter)
    : null;
  const clearLabel = reported ? 'Use printer value' : 'Clear designation';
  const options = [0.25, 0.4, 0.6, 0.8];
  return `<div class="material-designation-control nozzle-designation-control">
    <label>Controller nozzle designation
      <input type="number" data-nozzle-designation-input value="${escapeHtml(manualValue)}" list="flashforgeNozzleSizes" min="0.1" max="1.2" step="0.05" placeholder="e.g. 0.4" />
    </label>
    <datalist id="flashforgeNozzleSizes">${options.map((value) => `<option value="${value}"></option>`).join('')}</datalist>
    <div class="mini-actions"><button type="button" class="secondary" data-nozzle-designation-save>Assign nozzle</button><button type="button" class="secondary" data-nozzle-designation-clear>${escapeHtml(clearLabel)}</button></div>
    <div class="field-help">Stored by Printer Fleet Controller for this printer and used by automatic queue compatibility.${reported ? ` Printer currently reports ${escapeHtml(nozzleDiameterText(reported))}.` : ' FlashForge firmware does not reliably report the installed nozzle size, so set this whenever you change the nozzle.'}</div>
  </div>`;
}

function nozzleDiameterText(value) {""")
replace_once('public/app.js',
"""if (!tools.length) return `<div class="panel material-panel"><h3>Toolhead status</h3><div class="subtle">Material status is unavailable while the printer is offline.</div>${flashForgeMaterialDesignationMarkup(printer)}</div>`;""",
"""if (!tools.length) return `<div class="panel material-panel"><h3>Toolhead status</h3><div class="subtle">Material status is unavailable while the printer is offline.</div>${flashForgeMaterialDesignationMarkup(printer)}${flashForgeNozzleDesignationMarkup(printer)}</div>`;""")
replace_once('public/app.js',
"""      ${printer.adapterType === 'flashforge-ad5m' ? flashForgeMaterialDesignationMarkup(printer, tools[0]?.filament || {}) : ''}
      <div class="field-help material-help">${escapeHtml(materialHelp)}</div>""",
"""      ${printer.adapterType === 'flashforge-ad5m' ? flashForgeMaterialDesignationMarkup(printer, tools[0]?.filament || {}) : ''}
      ${printer.adapterType === 'flashforge-ad5m' ? flashForgeNozzleDesignationMarkup(printer, tools[0] || {}) : ''}
      <div class="field-help material-help">${escapeHtml(materialHelp)}</div>""")
replace_once('public/app.js',
"""      ? \"Filament type uses the controller's manual designation when set, otherwise the value reported by the FlashForge 5M local /detail API. The 5M API does not expose U1-style filament colour/RFID metadata or a reliable live filament-presence value, so those remain unknown.\"""",
"""      ? \"Filament type uses the controller's manual designation when set, otherwise the value reported by the FlashForge 5M local /detail API. Installed nozzle size uses the controller nozzle designation when set because the 5M API does not reliably expose it. The 5M API also does not expose U1-style filament colour/RFID metadata or a reliable live filament-presence value.\"""")
replace_once('public/app.js',
"""  printerDetail.querySelectorAll('[data-set-temp]').forEach((btn) => btn.onclick = () => {""",
"""  const nozzleDesignationSave = printerDetail.querySelector('[data-nozzle-designation-save]');
  if (nozzleDesignationSave) nozzleDesignationSave.onclick = async () => {
    const input = printerDetail.querySelector('[data-nozzle-designation-input]');
    const nozzleDiameter = Number(input?.value);
    if (!Number.isFinite(nozzleDiameter) || nozzleDiameter < 0.1 || nozzleDiameter > 1.2) {
      showError(new Error('Enter a nozzle diameter between 0.1 and 1.2 mm, or use Clear designation.'));
      return;
    }
    const original = nozzleDesignationSave.textContent;
    nozzleDesignationSave.disabled = true;
    nozzleDesignationSave.textContent = 'Saving…';
    try {
      const result = await api(`/api/printers/${id}/nozzle-designation`, { method:'POST', body:JSON.stringify({ nozzleDiameter }) });
      printer.nozzleDiameterDesignation = result.nozzleDiameterDesignation;
      const tool = printer.status?.tools?.[0];
      if (tool) {
        if (!Number.isFinite(Number(tool.reportedNozzleDiameter)) && tool.nozzleDiameterSource === 'printer' && Number.isFinite(Number(tool.nozzleDiameter))) {
          tool.reportedNozzleDiameter = Number(tool.nozzleDiameter);
        }
        tool.nozzleDiameter = result.nozzleDiameterDesignation;
        tool.nozzleDiameterSource = 'manual';
        tool.nozzleManuallyAssigned = true;
        updateOpenPrinterTelemetry();
      }
    } catch (error) { showError(error); }
    finally { nozzleDesignationSave.disabled = false; nozzleDesignationSave.textContent = original; }
  };
  const nozzleDesignationClear = printerDetail.querySelector('[data-nozzle-designation-clear]');
  if (nozzleDesignationClear) nozzleDesignationClear.onclick = async () => {
    const original = nozzleDesignationClear.textContent;
    nozzleDesignationClear.disabled = true;
    nozzleDesignationClear.textContent = 'Clearing…';
    try {
      await api(`/api/printers/${id}/nozzle-designation`, { method:'DELETE' });
      printer.nozzleDiameterDesignation = null;
      const tool = printer.status?.tools?.[0];
      if (tool) {
        const reported = Number(tool.reportedNozzleDiameter);
        tool.nozzleDiameter = Number.isFinite(reported) && reported > 0 ? reported : null;
        tool.nozzleDiameterSource = tool.nozzleDiameter ? 'printer' : null;
        tool.nozzleManuallyAssigned = false;
        updateOpenPrinterTelemetry();
      }
      const input = printerDetail.querySelector('[data-nozzle-designation-input]');
      if (input) input.value = '';
    } catch (error) { showError(error); }
    finally { nozzleDesignationClear.disabled = false; nozzleDesignationClear.textContent = original; }
  };

  printerDetail.querySelectorAll('[data-set-temp]').forEach((btn) => btn.onclick = () => {""")

replace_once('test/adapter-registry.test.js',
"""  assert.equal(adapter.capabilities.materialDesignation, true);
  assert.equal(adapter.limits.bedTemperature.max, 110);""",
"""  assert.equal(adapter.capabilities.materialDesignation, true);
  assert.equal(adapter.capabilities.nozzleDesignation, true);
  assert.equal(adapter.limits.bedTemperature.max, 110);""")
replace_once('test/adapter-registry.test.js',
"""test('FlashForge manual material designation overrides display value while retaining printer report', async () => {""",
"""test('FlashForge manual nozzle designation normalizes the installed nozzle for queue compatibility', async () => {
  const originalFetch = global.fetch;
  global.fetch = async () => ({
    ok:true,
    async json() { return { code:0, detail:{ status:'ready', rightFilamentType:'PLA' } }; }
  });
  try {
    const adapter = getPrinterAdapter({
      id:'p-nozzle', adapterType:FLASHFORGE_AD5M_ADAPTER_TYPE, host:'192.168.1.22',
      serialNumber:'SN', checkCode:'CODE', adapterConfig:{ nozzleDiameterDesignation:0.6 }
    });
    const status = await adapter.getStatus();
    assert.equal(status.tools[0].nozzleDiameter, 0.6);
    assert.equal(status.tools[0].nozzleDiameterSource, 'manual');
    assert.equal(status.tools[0].nozzleManuallyAssigned, true);
    assert.equal(status.tools[0].reportedNozzleDiameter, null);
  } finally {
    global.fetch = originalFetch;
  }
});

test('FlashForge manual material designation overrides display value while retaining printer report', async () => {""")

replace_once('test/store-order.test.js',
"""test('printer controller name can be renamed without changing connection identity', async () => {""",
"""test('FlashForge controller nozzle designation persists without exposing adapter secrets', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'ff-fleet-nozzle-designation-'));
  process.env.DATA_DIR = dir;
  const store = await import(`../src/store.js?nozzle-designation-test=${Date.now()}`);

  try {
    const printer = await store.addPrinter({
      name:'Nozzle Test', host:'10.0.3.2', serialNumber:'SN', checkCode:'CODE',
      adapterConfig:{ secretValue:'keep-private' }
    });
    const assigned = await store.setPrinterNozzleDesignation(printer.id, 0.6);
    assert.equal(assigned.adapterConfig.nozzleDiameterDesignation, 0.6);
    assert.equal(assigned.adapterConfig.secretValue, 'keep-private');
    assert.equal(store.publicPrinter(assigned).nozzleDiameterDesignation, 0.6);
    assert.equal('adapterConfig' in store.publicPrinter(assigned), false);
    await assert.rejects(() => store.setPrinterNozzleDesignation(printer.id, 2), /between 0.1 and 1.2 mm/);

    const cleared = await store.setPrinterNozzleDesignation(printer.id, null);
    assert.equal(cleared.adapterConfig.nozzleDiameterDesignation, undefined);
    assert.equal(cleared.adapterConfig.secretValue, 'keep-private');
    assert.equal(store.publicPrinter(cleared).nozzleDiameterDesignation, null);
  } finally {
    delete process.env.DATA_DIR;
    await rm(dir, { recursive:true, force:true });
  }
});

test('printer controller name can be renamed without changing connection identity', async () => {""")

replace_once('test/queue-compatibility.test.js',
"""test('automatic compatibility rejects file types unsupported by a printer adapter', () => {""",
"""test('FlashForge controller nozzle designation satisfies an explicit staged-file nozzle requirement', () => {
  const result = evaluateQueueCompatibility({
    job:{ fileName:'part.gcode', stagedFile:{ requirements:{ requiredTools:[0], toolCount:1, usageReliable:true, logicalTools:[{ index:0, material:'PLA', nozzleDiameter:0.6 }] } } },
    printer:{ id:'ff', name:'AD5M' },
    state:{ id:'ff', name:'AD5M', online:true, status:{ status:'idle', tools:[{ index:0, nozzleDiameter:0.6, nozzleDiameterSource:'manual', filament:{ material:'PLA' } }] } },
    adapter:{ capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true }, limits:{}, uploadExtensions:['.gcode','.gx','.3mf'] }
  });
  assert.equal(result.category, 'ready');
  assert.equal(result.reasons.length, 0);
});

test('FlashForge controller nozzle designation blocks an explicit nozzle mismatch', () => {
  const result = evaluateQueueCompatibility({
    job:{ fileName:'part.gcode', stagedFile:{ requirements:{ requiredTools:[0], toolCount:1, usageReliable:true, logicalTools:[{ index:0, material:'PLA', nozzleDiameter:0.6 }] } } },
    printer:{ id:'ff', name:'AD5M' },
    state:{ id:'ff', name:'AD5M', online:true, status:{ status:'idle', tools:[{ index:0, nozzleDiameter:0.4, nozzleDiameterSource:'manual', filament:{ material:'PLA' } }] } },
    adapter:{ capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true }, limits:{}, uploadExtensions:['.gcode','.gx','.3mf'] }
  });
  assert.equal(result.category, 'blocked');
  assert.ok(result.reasons.some((reason) => reason.code === 'nozzle_mismatch'));
});

test('automatic compatibility rejects file types unsupported by a printer adapter', () => {""")

replace_once('test/ui-print-setup.test.js',
"""test('FlashForge file material mismatch is warned for direct print and held for queue review', () => {""",
"""test('FlashForge detail exposes persistent controller nozzle designation for automatic queue compatibility', () => {
  const server = fs.readFileSync(new URL('../src/server.js', import.meta.url), 'utf8');
  const store = fs.readFileSync(new URL('../src/store.js', import.meta.url), 'utf8');
  const adapter = fs.readFileSync(new URL('../src/adapters/flashforge-ad5m-adapter.js', import.meta.url), 'utf8');
  assert.match(app, /Controller nozzle designation/);
  assert.match(app, /data-nozzle-designation-save/);
  assert.match(app, /data-nozzle-designation-clear/);
  assert.match(app, /\/api\/printers\/\$\{id\}\/nozzle-designation/);
  assert.match(server, /action === 'nozzle-designation'/);
  assert.match(store, /setPrinterNozzleDesignation/);
  assert.match(adapter, /nozzleDiameterDesignation/);
  assert.match(adapter, /nozzleDiameterSource = 'manual'/);
});

test('FlashForge file material mismatch is warned for direct print and held for queue review', () => {""")

replace_once('package.json', '"version": "0.11.0"', '"version": "0.11.1"')
replace_once('README.md', '# Printer Fleet Controller v0.11.0\n', '# Printer Fleet Controller v0.11.1\n\n> v0.11.1 adds a persistent **Controller nozzle designation** for FlashForge 5M-family printers. Set the installed nozzle diameter in Toolhead status so file-centric automatic queue compatibility can safely match staged G-code nozzle requirements instead of holding FlashForge jobs for review when the local API cannot report nozzle size.\n')
replace_once('PROJECT_CONTEXT.md', 'Current application version: **0.11.0**', 'Current application version: **0.11.1**')
replace_once('PROJECT_CONTEXT.md',
"""- v0.11.0 regression suite: **100 passing tests, 0 failures**, including GitHub Actions verification of the release patch.

## Current task""",
"""- v0.11.0 regression suite: **100 passing tests, 0 failures**, including GitHub Actions verification of the release patch.
- **v0.11.1 FlashForge nozzle designation:** persistent per-printer controller nozzle diameter, normalized into FlashForge tool status and enforced by file-centric automatic queue compatibility; explicit nozzle matches can run unattended and mismatches are blocked.

## Current task""")
replace_once('PROJECT_CONTEXT.md',
"""**v0.11.0 implementation is complete in code and automated tests.** Next priority is real-hardware validation of the new **Next available compatible printer** workflow on the user's configured FlashForge and Snapmaker fleet.""",
"""**v0.11.1 implementation is complete in code and automated tests.** Next priority is real-hardware validation of the **Next available compatible printer** workflow, including the new FlashForge controller nozzle designation, on the user's configured FlashForge and Snapmaker fleet.""")
replace_once('PROJECT_CONTEXT.md',
"""5. Confirm FlashForge files with explicit nozzle requirements enter **Needs review** when nozzle size cannot be verified rather than being started automatically.""",
"""5. Set each FlashForge printer's **Controller nozzle designation**, then confirm explicit staged-file nozzle matches become eligible and mismatches remain blocked; clearing the designation should return explicit-nozzle jobs to **Needs review**.""")
