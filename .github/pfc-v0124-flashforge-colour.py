from pathlib import Path
import re

ROOT = Path('print-farm-controller')

def replace_once(rel, old, new):
    path = ROOT / rel
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{rel}: expected one patch target, found {count}: {old[:100]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

def regex_once(rel, pattern, replacement):
    path = ROOT / rel
    text = path.read_text(encoding='utf-8')
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f'{rel}: regex patch target not found: {pattern[:100]!r}')
    path.write_text(new, encoding='utf-8')

replace_once('package.json', '"version": "0.12.3"', '"version": "0.12.4"')

# Persistent FlashForge filament colour designation.
replace_once('src/store.js',
'''function normalizeMaterialDesignation(value) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  if (text.length > 48) throw new Error('Material designation must be 48 characters or fewer');
  if (/[\\x00-\\x1f\\x7f]/.test(text)) throw new Error('Material designation contains invalid characters');
  return text;
}

function normalizeNozzleDesignation(value) {''',
'''function normalizeMaterialDesignation(value) {
  const text = String(value ?? '').trim();
  if (!text) return null;
  if (text.length > 48) throw new Error('Material designation must be 48 characters or fewer');
  if (/[\\x00-\\x1f\\x7f]/.test(text)) throw new Error('Material designation contains invalid characters');
  return text;
}

function normalizeColorDesignation(value) {
  if (value == null || String(value).trim() === '') return null;
  const text = String(value).trim().replace(/^0x/i, '').replace(/^#/, '').toUpperCase();
  if (!/^[0-9A-F]{6}$/.test(text)) throw new Error('Filament colour must be a 6-digit hex colour');
  return `#${text}`;
}

function normalizeNozzleDesignation(value) {''')

regex_once('src/store.js',
r'''export async function setPrinterMaterialDesignation\(id, material\) \{.*?\n\}\n\nexport async function setPrinterNozzleDesignation''',
'''export async function setPrinterMaterialDesignation(id, material, color = undefined) {
  const printers = await readAll();
  const index = printers.findIndex((printer) => printer.id === id);
  if (index < 0) return null;

  const designation = normalizeMaterialDesignation(material);
  const colorDesignation = color === undefined ? undefined : normalizeColorDesignation(color);
  const adapterConfig = { ...(printers[index].adapterConfig || {}) };
  if (designation) adapterConfig.filamentDesignation = designation;
  else delete adapterConfig.filamentDesignation;
  if (colorDesignation !== undefined) {
    if (colorDesignation) adapterConfig.filamentColorDesignation = colorDesignation;
    else delete adapterConfig.filamentColorDesignation;
  }

  printers[index] = { ...printers[index], adapterConfig };
  await writeAll(printers);
  return normalizeStoredPrinter(printers[index]);
}

export async function setPrinterNozzleDesignation''')

replace_once('src/store.js',
'''    materialDesignation: String(printer.adapterConfig?.filamentDesignation || '').trim() || null,
    nozzleDiameterDesignation: Number.isFinite(Number(printer.adapterConfig?.nozzleDiameterDesignation))''',
'''    materialDesignation: String(printer.adapterConfig?.filamentDesignation || '').trim() || null,
    materialColorDesignation: normalizeColorDesignation(printer.adapterConfig?.filamentColorDesignation),
    nozzleDiameterDesignation: Number.isFinite(Number(printer.adapterConfig?.nozzleDiameterDesignation))''')

# Apply controller material + colour into normalized FlashForge tool state.
replace_once('src/adapters/flashforge-ad5m-adapter.js',
'''    const filament = status?.tools?.[0]?.filament;
    if (filament) {
      const reportedMaterial = filament.material || null;
      const manualMaterial = String(this.printer.adapterConfig?.filamentDesignation || '').trim() || null;
      filament.reportedMaterial = reportedMaterial;
      if (manualMaterial) {
        filament.material = manualMaterial;
        filament.materialSource = 'manual';
        filament.manuallyAssigned = true;
        filament.metadataAvailable = true;
      } else {
        filament.manuallyAssigned = false;
      }
    }
''',
'''    const filament = status?.tools?.[0]?.filament;
    if (filament) {
      const reportedMaterial = filament.material || null;
      const reportedColor = filament.color || null;
      const manualMaterial = String(this.printer.adapterConfig?.filamentDesignation || '').trim() || null;
      const manualColorRaw = String(this.printer.adapterConfig?.filamentColorDesignation || '').trim();
      const manualColor = /^#[0-9A-Fa-f]{6}$/.test(manualColorRaw) ? manualColorRaw.toUpperCase() : null;
      filament.reportedMaterial = reportedMaterial;
      filament.reportedColor = reportedColor;
      if (manualMaterial) {
        filament.material = manualMaterial;
        filament.materialSource = 'manual';
      }
      if (manualColor) {
        filament.color = manualColor;
        filament.colorSource = 'manual';
      }
      filament.manuallyAssigned = Boolean(manualMaterial || manualColor);
      if (manualMaterial || manualColor) filament.metadataAvailable = true;
    }
''')

# Existing material endpoint now also persists/returns colour while remaining backwards compatible.
replace_once('src/server.js',
'''    const updated = await setPrinterMaterialDesignation(id, req.method === 'POST' ? body.material : null);
    if (!updated) throw new Error('Printer not found');
    await fleetState.syncRegistry();
    fleetState.refreshNow(id).catch(() => {});
    return json(res, 200, { ok: true, printer: publicPrinter(updated), materialDesignation: updated.adapterConfig?.filamentDesignation || null });
''',
'''    const updated = await setPrinterMaterialDesignation(
      id,
      req.method === 'POST' ? body.material : null,
      req.method === 'POST' ? body.color : null
    );
    if (!updated) throw new Error('Printer not found');
    await fleetState.syncRegistry();
    fleetState.refreshNow(id).catch(() => {});
    return json(res, 200, {
      ok: true,
      printer: publicPrinter(updated),
      materialDesignation: updated.adapterConfig?.filamentDesignation || null,
      materialColorDesignation: updated.adapterConfig?.filamentColorDesignation || null
    });
''')

# FlashForge detail control: material type + colour picker saved together.
regex_once('public/app.js',
r'''function flashForgeMaterialDesignationMarkup\(printer, filament = \{\}\) \{.*?\n\}\n\nfunction flashForgeNozzleDesignationMarkup''',
'''function flashForgeMaterialDesignationMarkup(printer, filament = {}) {
  if (!printer?.capabilities?.materialDesignation) return '';
  const manualValue = filament.materialSource === 'manual'
    ? String(filament.material || '')
    : String(printer.materialDesignation || '');
  const manualColor = filament.colorSource === 'manual'
    ? String(filament.color || '')
    : String(printer.materialColorDesignation || '');
  const colorValue = /^#[0-9A-Fa-f]{6}$/.test(manualColor) ? manualColor : '#FFFFFF';
  const reported = filament.reportedMaterial || (filament.materialSource === 'printer' ? filament.material : null);
  const clearLabel = reported ? 'Use printer value' : 'Clear designation';
  const options = ['PLA','PETG','ABS','ASA','TPU','PC','PA','Nylon','PVA','HIPS','PP','PET','PLA-CF','PETG-CF','ASA-CF','PA-CF','PC-CF'];
  return `<div class="material-designation-control">
    <div class="material-designation-fields">
      <label>Controller material type
        <input type="text" data-material-designation-input value="${escapeHtml(manualValue)}" list="flashforgeMaterialTypes" maxlength="48" placeholder="e.g. PLA, PETG, ASA" autocomplete="off" />
      </label>
      <label>Controller filament colour
        <input type="color" data-material-color-input value="${escapeHtml(colorValue)}" aria-label="Controller filament colour" />
      </label>
    </div>
    <datalist id="flashforgeMaterialTypes">${options.map((value) => `<option value="${escapeHtml(value)}"></option>`).join('')}</datalist>
    <div class="mini-actions"><button type="button" class="secondary" data-material-designation-save>Assign filament</button><button type="button" class="secondary" data-material-designation-clear>${escapeHtml(clearLabel)}</button></div>
    <div class="field-help">Stored by Printer Fleet Controller for this printer. Material and colour are used by automatic queue compatibility until cleared.${reported ? ` Printer currently reports material ${escapeHtml(reported)}.` : ''}</div>
  </div>`;
}

function flashForgeNozzleDesignationMarkup''')

regex_once('public/app.js',
r'''  const materialDesignationSave = printerDetail\.querySelector\('\[data-material-designation-save\]'\);.*?\n\n  const nozzleDesignationSave =''',
'''  const materialDesignationSave = printerDetail.querySelector('[data-material-designation-save]');
  if (materialDesignationSave) materialDesignationSave.onclick = async () => {
    const input = printerDetail.querySelector('[data-material-designation-input]');
    const colorInput = printerDetail.querySelector('[data-material-color-input]');
    const material = String(input?.value || '').trim();
    const color = String(colorInput?.value || '').trim().toUpperCase();
    if (!material) { showError(new Error('Enter a material type to assign, or use Clear designation.')); return; }
    if (!/^#[0-9A-F]{6}$/.test(color)) { showError(new Error('Choose a filament colour.')); return; }
    const original = materialDesignationSave.textContent;
    materialDesignationSave.disabled = true;
    materialDesignationSave.textContent = 'Saving…';
    try {
      await api(`/api/printers/${id}/material-designation`, { method:'POST', body: JSON.stringify({ material, color }) });
      printer.materialDesignation = material;
      printer.materialColorDesignation = color;
      const filament = printer.status?.tools?.[0]?.filament;
      if (filament) {
        if (!filament.reportedMaterial && filament.materialSource === 'printer') filament.reportedMaterial = filament.material || null;
        if (!filament.reportedColor && filament.colorSource === 'printer') filament.reportedColor = filament.color || null;
        filament.material = material;
        filament.materialSource = 'manual';
        filament.color = color;
        filament.colorSource = 'manual';
        filament.manuallyAssigned = true;
        filament.metadataAvailable = true;
        updateOpenPrinterTelemetry();
      }
    } catch (error) { showError(error); }
    finally { materialDesignationSave.disabled = false; materialDesignationSave.textContent = original; }
  };
  const materialDesignationClear = printerDetail.querySelector('[data-material-designation-clear]');
  if (materialDesignationClear) materialDesignationClear.onclick = async () => {
    const original = materialDesignationClear.textContent;
    materialDesignationClear.disabled = true;
    materialDesignationClear.textContent = 'Clearing…';
    try {
      await api(`/api/printers/${id}/material-designation`, { method:'DELETE' });
      printer.materialDesignation = null;
      printer.materialColorDesignation = null;
      const filament = printer.status?.tools?.[0]?.filament;
      if (filament) {
        filament.material = filament.reportedMaterial || null;
        filament.materialSource = filament.reportedMaterial ? 'printer' : null;
        filament.color = filament.reportedColor || null;
        filament.colorSource = filament.reportedColor ? 'printer' : null;
        filament.manuallyAssigned = false;
        updateOpenPrinterTelemetry();
      }
      const input = printerDetail.querySelector('[data-material-designation-input]');
      if (input) input.value = '';
      const colorInput = printerDetail.querySelector('[data-material-color-input]');
      if (colorInput) colorInput.value = '#FFFFFF';
    } catch (error) { showError(error); }
    finally { materialDesignationClear.disabled = false; materialDesignationClear.textContent = original; }
  };

  const nozzleDesignationSave =''')

replace_once('public/styles.css',
'''.material-designation-control input { margin-top:6px; }
.material-designation-control .field-help { margin-top:8px; }
''',
'''.material-designation-control input { margin-top:6px; }
.material-designation-fields { display:grid; grid-template-columns:minmax(0,1fr) 132px; gap:10px; align-items:end; }
.material-designation-fields label { margin-top:0; }
.material-designation-fields input[type="color"] { min-height:44px; padding:5px; cursor:pointer; }
.material-designation-control .field-help { margin-top:8px; }
@media (max-width:520px) { .material-designation-fields { grid-template-columns:1fr; gap:0; } }
''')

# Regression tests.
replace_once('test/store-order.test.js',
'''    const assigned = await store.setPrinterMaterialDesignation(printer.id, 'PETG-CF');
    assert.equal(assigned.adapterConfig.filamentDesignation, 'PETG-CF');
    assert.equal(assigned.adapterConfig.secretValue, 'keep-private');
    assert.equal(store.publicPrinter(assigned).materialDesignation, 'PETG-CF');
    assert.equal('adapterConfig' in store.publicPrinter(assigned), false);

    const cleared = await store.setPrinterMaterialDesignation(printer.id, null);
    assert.equal(cleared.adapterConfig.filamentDesignation, undefined);
    assert.equal(cleared.adapterConfig.secretValue, 'keep-private');
    assert.equal(store.publicPrinter(cleared).materialDesignation, null);
''',
'''    const assigned = await store.setPrinterMaterialDesignation(printer.id, 'PETG-CF', '#12ab34');
    assert.equal(assigned.adapterConfig.filamentDesignation, 'PETG-CF');
    assert.equal(assigned.adapterConfig.filamentColorDesignation, '#12AB34');
    assert.equal(assigned.adapterConfig.secretValue, 'keep-private');
    assert.equal(store.publicPrinter(assigned).materialDesignation, 'PETG-CF');
    assert.equal(store.publicPrinter(assigned).materialColorDesignation, '#12AB34');
    assert.equal('adapterConfig' in store.publicPrinter(assigned), false);
    await assert.rejects(() => store.setPrinterMaterialDesignation(printer.id, 'PETG-CF', 'green'), /6-digit hex colour/);

    const cleared = await store.setPrinterMaterialDesignation(printer.id, null, null);
    assert.equal(cleared.adapterConfig.filamentDesignation, undefined);
    assert.equal(cleared.adapterConfig.filamentColorDesignation, undefined);
    assert.equal(cleared.adapterConfig.secretValue, 'keep-private');
    assert.equal(store.publicPrinter(cleared).materialDesignation, null);
    assert.equal(store.publicPrinter(cleared).materialColorDesignation, null);
''')

replace_once('test/adapter-registry.test.js',
'''      serialNumber:'SN', checkCode:'CODE', adapterConfig:{ filamentDesignation:'PETG' }
    });
    const status = await adapter.getStatus();
    const filament = status.tools[0].filament;
    assert.equal(filament.material, 'PETG');
    assert.equal(filament.materialSource, 'manual');
    assert.equal(filament.manuallyAssigned, true);
    assert.equal(filament.reportedMaterial, 'PLA');
''',
'''      serialNumber:'SN', checkCode:'CODE', adapterConfig:{ filamentDesignation:'PETG', filamentColorDesignation:'#3366cc' }
    });
    const status = await adapter.getStatus();
    const filament = status.tools[0].filament;
    assert.equal(filament.material, 'PETG');
    assert.equal(filament.materialSource, 'manual');
    assert.equal(filament.color, '#3366CC');
    assert.equal(filament.colorSource, 'manual');
    assert.equal(filament.manuallyAssigned, true);
    assert.equal(filament.reportedMaterial, 'PLA');
    assert.equal(filament.reportedColor, null);
''')

# Add direct proof that a controller-assigned FlashForge colour participates in auto compatibility.
q = ROOT / 'test/queue-compatibility.test.js'
text = q.read_text(encoding='utf-8')
marker = "\ntest('automatic compatibility rejects file types unsupported by a printer adapter', () => {"
if marker not in text:
    raise SystemExit('queue compatibility insertion marker missing')
new_test = '''\n\ntest('FlashForge controller filament colour blocks an explicit staged-file colour mismatch', () => {
  const result = evaluateQueueCompatibility({
    job:{ fileName:'part.gcode', stagedFile:{ requirements:{ requiredTools:[0], toolCount:1, usageReliable:true, logicalTools:[{ index:0, material:'PLA', color:'#FF0000' }] } } },
    printer:{ id:'ff', name:'AD5M' },
    state:{ id:'ff', name:'AD5M', online:true, status:{ status:'idle', tools:[{ index:0, filament:{ material:'PLA', color:'#0000FF', colorSource:'manual' } }] } },
    adapter:{ capabilities:{ fileUpload:true, localFiles:true, printLocalFile:true }, limits:{}, uploadExtensions:['.gcode','.gx','.3mf'] }
  });
  assert.equal(result.category, 'blocked');
  assert.ok(result.reasons.some((reason) => reason.code === 'color_mismatch'));
});
'''
q.write_text(text.replace(marker, new_test + marker, 1), encoding='utf-8')

replace_once('test/ui-print-setup.test.js',
'''  assert.match(app, /Controller material designation/);
  assert.match(app, /'ASA-CF'/);
  assert.match(app, /data-material-designation-save/);
  assert.match(app, /data-material-designation-clear/);
  assert.match(app, /Printer reports/);
''',
'''  assert.match(app, /Controller material type/);
  assert.match(app, /Controller filament colour/);
  assert.match(app, /data-material-color-input/);
  assert.match(app, /materialColorDesignation/);
  assert.match(app, /'ASA-CF'/);
  assert.match(app, /data-material-designation-save/);
  assert.match(app, /data-material-designation-clear/);
  assert.match(app, /Material and colour are used by automatic queue compatibility/);
''')

# README/context release notes.
replace_once('README.md', '# Printer Fleet Controller v0.12.3', '# Printer Fleet Controller v0.12.4')
readme = ROOT / 'README.md'
text = readme.read_text(encoding='utf-8')
needle = '# Printer Fleet Controller v0.12.4\n\n'
if needle not in text:
    raise SystemExit('README header insertion point missing')
text = text.replace(needle, needle + '> v0.12.4 adds a persistent **filament colour designation** alongside material type for FlashForge printers. The printer window now provides a colour picker; the controller-normalized tool state and automatic queue compatibility use the assigned colour, including blocking explicit colour mismatches.\n\n', 1)
readme.write_text(text, encoding='utf-8')

ctx = ROOT / 'PROJECT_CONTEXT.md'
text = ctx.read_text(encoding='utf-8')
text = text.replace('Current application version: **0.12.3**', 'Current application version: **0.12.4**', 1)
anchor = '- v0.12.3 regression suite: **119 passing tests, 0 failures**.\n'
if anchor not in text:
    raise SystemExit('PROJECT_CONTEXT release anchor missing')
text = text.replace(anchor, anchor + '- **v0.12.4 FlashForge filament colour designation:** FlashForge printer detail controls now persist both material type and `#RRGGBB` filament colour; the assigned colour is normalized into tool status and participates in automatic queue compatibility/mismatch blocking.\n', 1)
text = re.sub(r'## Current task\n\n.*?\n\n## Next steps', '## Current task\n\n**v0.12.4 FlashForge filament colour designation is complete in code and automated tests.** Next priority is real-hardware validation that material/colour assignments render correctly and influence automatic compatibility as expected.\n\n## Next steps', text, count=1, flags=re.S)
ctx.write_text(text, encoding='utf-8')
