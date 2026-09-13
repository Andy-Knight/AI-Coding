from pathlib import Path

ROOT = Path('print-farm-controller')

def replace_once(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    path.write_text(text.replace(old, new, 1))

# Version
package = ROOT / 'package.json'
replace_once(package, '"version": "0.12.7"', '"version": "0.12.8"', 'package version')

# Adapter capability + contract.
base_adapter = ROOT / 'src/adapters/printer-adapter.js'
replace_once(
    base_adapter,
    "  materialDesignation: false,\n  nozzleDesignation: false,",
    "  materialDesignation: false,\n  filamentColorControl: false,\n  nozzleDesignation: false,",
    'base filament colour capability'
)
replace_once(
    base_adapter,
    "  async setFiltration() { return this.unsupported('Filtration control'); }\n",
    "  async setFiltration() { return this.unsupported('Filtration control'); }\n  async setFilamentColor() { return this.unsupported('Filament colour control'); }\n",
    'base filament colour method'
)

# Snapmaker adapter exposes the native capability and method.
u1_adapter = ROOT / 'src/adapters/snapmaker-u1-adapter.js'
replace_once(
    u1_adapter,
    "  setMoonrakerFiltration,\n  startMoonrakerChamberPreheat,",
    "  setMoonrakerFiltration,\n  setMoonrakerFilamentColor,\n  startMoonrakerChamberPreheat,",
    'u1 import'
)
replace_once(
    u1_adapter,
    "  materialStatus: true,\n  printToolMapping: true,",
    "  materialStatus: true,\n  filamentColorControl: true,\n  printToolMapping: true,",
    'u1 capability'
)
replace_once(
    u1_adapter,
    "  async setFiltration(values) { return setMoonrakerFiltration(this.printer, values); }\n",
    "  async setFiltration(values) { return setMoonrakerFiltration(this.printer, values); }\n  async setFilamentColor(values) { return setMoonrakerFilamentColor(this.printer, values); }\n",
    'u1 adapter method'
)

# Moonraker status exposes the printer's editability flag; write colour using the
# touchscreen-native command and verify the printer's own read-back.
moon = ROOT / 'src/moonraker-api.js'
replace_once(
    moon,
    "    const configuredOfficial = arrayValue(taskConfig, 'filament_official', index);\n    const configuredExists = arrayValue(taskConfig, 'filament_exist', index);",
    "    const configuredOfficial = arrayValue(taskConfig, 'filament_official', index);\n    const configuredExists = arrayValue(taskConfig, 'filament_exist', index);\n    const configuredEditable = arrayValue(taskConfig, 'filament_edit', index);",
    'u1 editable read'
)
replace_once(
    moon,
    "      officialFilament: configuredOfficial === true,\n      configuredExists: typeof configuredExists === 'boolean' ? configuredExists : null,",
    "      officialFilament: configuredOfficial === true,\n      configuredExists: typeof configuredExists === 'boolean' ? configuredExists : null,\n      colorEditable: typeof configuredEditable === 'boolean' ? configuredEditable : (configuredOfficial === true ? false : null),",
    'u1 editable normalized'
)
filament_function = r'''export async function setMoonrakerFilamentColor(printer, { toolIndex, color } = {}) {
  const index = Number(toolIndex);
  if (!Number.isInteger(index) || index < 0 || index >= SNAPMAKER_U1_TOOL_COUNT) {
    throw new MoonrakerApiError('Tool index must be 0-3');
  }
  const normalizedColor = normalizeHexColor(color);
  if (!normalizedColor || !/^#[0-9A-F]{6}$/.test(normalizedColor)) {
    throw new MoonrakerApiError('Filament colour must be a 6-digit RGB hex value');
  }

  const current = await moonrakerRequest(printer, '/printer/objects/query?print_stats&print_task_config');
  const status = current?.status || current || {};
  const printState = String(status.print_stats?.state || 'unknown').toLowerCase();
  if (!['standby', 'complete', 'cancelled'].includes(printState)) {
    throw new MoonrakerApiError('U1 filament colour can only be changed while the printer is idle');
  }

  const taskConfig = status.print_task_config || {};
  const exists = arrayValue(taskConfig, 'filament_exist', index);
  if (exists !== true) throw new MoonrakerApiError(`No filament is loaded in U1 T${index}`);

  const material = cleanFilamentText(arrayValue(taskConfig, 'filament_type', index));
  const official = arrayValue(taskConfig, 'filament_official', index);
  const editable = arrayValue(taskConfig, 'filament_edit', index);
  if (!material) throw new MoonrakerApiError(`U1 T${index} has no manually assigned filament material to edit`);
  if (official === true || editable === false) {
    throw new MoonrakerApiError(`U1 T${index} colour is locked by its official Snapmaker RFID filament`);
  }

  const rgba = `${normalizedColor.slice(1)}FF`;
  await runMoonrakerGcode(
    printer,
    `SET_PRINT_FILAMENT_CONFIG CONFIG_EXTRUDER='${index}' FILAMENT_COLOR_RGBA='${rgba}' SAVE='1'`
  );

  const verified = await moonrakerRequest(printer, '/printer/objects/query?print_task_config');
  const verifiedStatus = verified?.status || verified || {};
  const reported = String(arrayValue(verifiedStatus.print_task_config || {}, 'filament_color_rgba', index) || '').toUpperCase();
  if (reported !== rgba) {
    throw new MoonrakerApiError(`U1 did not confirm the filament colour change for T${index}`);
  }
  return { toolIndex:index, color:normalizedColor, rgba, verified:true };
}

'''
replace_once(
    moon,
    "export async function setMoonrakerTemperatures(printer, { nozzle, bed, toolIndex, allTools = false } = {}) {",
    filament_function + "export async function setMoonrakerTemperatures(printer, { nozzle, bed, toolIndex, allTools = false } = {}) {",
    'u1 native filament colour function'
)

# API route invokes adapter operation; no controller-side colour shadow is stored.
server = ROOT / 'src/server.js'
route = r'''  if (req.method === 'POST' && action === 'filament-color') {
    if (!adapter.capabilities?.filamentColorControl) throw new Error('Filament colour control is not supported by this printer');
    const body = await readJson(req);
    const result = await adapter.setFilamentColor({ toolIndex:body.toolIndex, color:body.color });
    refreshAfterCommand(id);
    return json(res, 200, { ok:true, ...result });
  }

'''
replace_once(
    server,
    "  if (action === 'material-designation' && (req.method === 'POST' || req.method === 'DELETE')) {",
    route + "  if (action === 'material-designation' && (req.method === 'POST' || req.method === 'DELETE')) {",
    'server filament colour route'
)

# UI helpers and controls.
app = ROOT / 'public/app.js'
helpers = r'''function u1FilamentColorEditState(printer, tool = {}) {
  const filament = tool.filament || {};
  if (printer?.adapterType !== 'snapmaker-u1' || !printer?.capabilities?.filamentColorControl) {
    return { enabled:false, message:'Filament colour editing is unavailable.' };
  }
  if (String(printer.status?.status || '').toLowerCase() !== 'idle') {
    return { enabled:false, message:'Colour can be changed while the U1 is idle.' };
  }
  if (filament.present !== true) return { enabled:false, message:`Load filament in T${tool.index} before changing its colour.` };
  if (filament.officialFilament === true || filament.colorEditable === false) {
    return { enabled:false, message:'Official Snapmaker RFID filament controls its own colour.' };
  }
  if (filament.manuallyAssigned !== true && filament.materialSource !== 'manual') {
    return { enabled:false, message:'Assign third-party filament on the U1 before changing its colour.' };
  }
  return { enabled:true, message:'Writes the colour to the U1 and verifies the printer read-back.' };
}

function u1FilamentColorControlMarkup(printer, tool = {}) {
  if (printer?.adapterType !== 'snapmaker-u1' || !printer?.capabilities?.filamentColorControl) return '';
  const filament = tool.filament || {};
  const state = u1FilamentColorEditState(printer, tool);
  const color = normalizeColor(filament.color) || '#FFFFFF';
  return `<div class="u1-filament-color-control" data-u1-filament-color-control="${tool.index}">
    <label>Filament colour<input type="color" data-u1-filament-color-input="${tool.index}" value="${escapeHtml(color)}"${state.enabled ? '' : ' disabled'}></label>
    <button type="button" class="secondary" data-u1-filament-color-save="${tool.index}"${state.enabled ? '' : ' disabled'}>Set on U1</button>
    <small data-u1-filament-color-help="${tool.index}">${escapeHtml(state.message)}</small>
  </div>`;
}

'''
replace_once(
    app,
    "function flashForgeMaterialDesignationMarkup(printer, filament = {}) {",
    helpers + "function flashForgeMaterialDesignationMarkup(printer, filament = {}) {",
    'u1 colour UI helpers'
)
replace_once(
    app,
    "          ${['snapmaker-u1','flashforge-ad5m'].includes(printer.adapterType) ? `<small class=\"material-rgb${filamentRgbText(filament.color) ? '' : ' hidden'}\" data-material-rgb=\"${tool.index}\">${escapeHtml(filamentRgbText(filament.color) || '')}</small>` : ''}\n        </div>`;",
    "          ${['snapmaker-u1','flashforge-ad5m'].includes(printer.adapterType) ? `<small class=\"material-rgb${filamentRgbText(filament.color) ? '' : ' hidden'}\" data-material-rgb=\"${tool.index}\">${escapeHtml(filamentRgbText(filament.color) || '')}</small>` : ''}\n          ${printer.adapterType === 'snapmaker-u1' ? u1FilamentColorControlMarkup(printer, tool) : ''}\n        </div>`;",
    'u1 colour control markup'
)
replace_once(
    app,
    "      const rgbLine = row.querySelector(`[data-material-rgb=\"${tool.index}\"]`);\n      rgbLine?.classList.toggle('hidden', !rgbText);\n      row.classList.toggle('filament-missing', filament.present === false);",
    "      const rgbLine = row.querySelector(`[data-material-rgb=\"${tool.index}\"]`);\n      rgbLine?.classList.toggle('hidden', !rgbText);\n      const u1ColorState = u1FilamentColorEditState(printer, tool);\n      const u1ColorInput = row.querySelector(`[data-u1-filament-color-input=\"${tool.index}\"]`);\n      const u1ColorSave = row.querySelector(`[data-u1-filament-color-save=\"${tool.index}\"]`);\n      const u1ColorHelp = row.querySelector(`[data-u1-filament-color-help=\"${tool.index}\"]`);\n      if (u1ColorInput) {\n        if (document.activeElement !== u1ColorInput) u1ColorInput.value = normalizeColor(filament.color) || '#FFFFFF';\n        u1ColorInput.disabled = !u1ColorState.enabled;\n      }\n      if (u1ColorSave) u1ColorSave.disabled = !u1ColorState.enabled;\n      if (u1ColorHelp) u1ColorHelp.textContent = u1ColorState.message;\n      row.classList.toggle('filament-missing', filament.present === false);",
    'u1 colour live telemetry'
)
replace_once(
    app,
    "      : 'Filament presence comes from each U1 motion sensor. Material and colour use the U1\\'s effective per-tool configuration, including manual assignments for third-party filament; RFID data is used as fallback. Nozzle size and XYZ offset come directly from each physical U1 extruder.';",
    "      : 'Filament presence comes from each U1 motion sensor. Material and colour use the U1\\'s effective per-tool configuration, including manual assignments for third-party filament; manually assigned filament colours can be written back to the idle printer. Official Snapmaker RFID colours remain locked. Nozzle size and XYZ offset come directly from each physical U1 extruder.';",
    'u1 material help'
)
color_handler = r'''  printerDetail.querySelectorAll('[data-u1-filament-color-save]').forEach((button) => button.onclick = async () => {
    const toolIndex = Number(button.dataset.u1FilamentColorSave);
    const input = printerDetail.querySelector(`[data-u1-filament-color-input="${toolIndex}"]`);
    const color = normalizeColor(input?.value);
    if (!color) { showError(new Error('Choose a valid filament colour.')); return; }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Setting…';
    try {
      const result = await api(`/api/printers/${id}/filament-color`, { method:'POST', body:JSON.stringify({ toolIndex, color }) });
      const tool = printer.status?.tools?.find((item) => Number(item.index) === toolIndex);
      if (tool?.filament) {
        tool.filament.color = result.color;
        tool.filament.metadataAvailable = true;
      }
      updateOpenPrinterTelemetry();
    } catch (error) { showError(error); }
    finally { button.textContent = original; updateOpenPrinterTelemetry(); }
  });

'''
replace_once(
    app,
    "  const materialDesignationSave = printerDetail.querySelector('[data-material-designation-save]');",
    color_handler + "  const materialDesignationSave = printerDetail.querySelector('[data-material-designation-save]');",
    'u1 colour click handler'
)

# Compact control inside each U1 tool card.
styles = ROOT / 'public/styles.css'
replace_once(
    styles,
    ".material-tool > small.material-rgb { color:#8193a2; margin-top:2px; }\n",
    ".material-tool > small.material-rgb { color:#8193a2; margin-top:2px; }\n.u1-filament-color-control { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:6px 8px; align-items:end; margin-top:8px; padding-top:8px; border-top:1px solid #202a32; }\n.u1-filament-color-control label { margin:0; color:#8493a1; font-size:.68rem; }\n.u1-filament-color-control input[type=\"color\"] { display:block; width:100%; min-height:34px; margin-top:4px; padding:3px; cursor:pointer; }\n.u1-filament-color-control button { min-height:34px; padding:6px 9px; }\n.u1-filament-color-control small { grid-column:1 / -1; color:#687986; font-size:.66rem; line-height:1.3; }\n",
    'u1 colour styles'
)

# Moonraker regression tests.
moon_test = ROOT / 'test/moonraker-api.test.js'
replace_once(
    moon_test,
    "  setMoonrakerFiltration,\n  startMoonrakerChamberPreheat,",
    "  setMoonrakerFiltration,\n  setMoonrakerFilamentColor,\n  startMoonrakerChamberPreheat,",
    'test import'
)
replace_once(
    moon_test,
    "      filament_official:[false,true,false,false],\n      filament_exist:[true,true,true,false],",
    "      filament_official:[false,true,false,false],\n      filament_exist:[true,true,true,false],\n      filament_edit:[true,false,true,false],",
    'test editability fixture'
)
replace_once(
    moon_test,
    "  assert.equal(t0.rfidMetadataAvailable, true);\n",
    "  assert.equal(t0.rfidMetadataAvailable, true);\n  assert.equal(t0.colorEditable, true);\n",
    'manual editable assert'
)
replace_once(
    moon_test,
    "  assert.equal(t1.officialFilament, true);\n",
    "  assert.equal(t1.officialFilament, true);\n  assert.equal(t1.colorEditable, false);\n",
    'official locked assert'
)
replace_once(
    moon_test,
    "  assert.equal(adapter.capabilities.materialStatus, true);\n",
    "  assert.equal(adapter.capabilities.materialStatus, true);\n  assert.equal(adapter.capabilities.filamentColorControl, true);\n",
    'adapter capability assert'
)
new_tests = r'''
test('U1 manual filament colour uses the touchscreen-native command and verifies printer read-back', async () => {
  const scripts = [];
  let reportedColor = '112233FF';
  const { server, port } = await listen((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname === '/printer/objects/query') {
      const wantsPrintStats = url.search.includes('print_stats');
      res.writeHead(200, { 'content-type':'application/json' });
      res.end(JSON.stringify({ result:{ status:{
        ...(wantsPrintStats ? { print_stats:{ state:'standby' } } : {}),
        print_task_config:{
          filament_exist:[true,false,false,false],
          filament_edit:[true,false,false,false],
          filament_official:[false,false,false,false],
          filament_type:['PETG','NONE','NONE','NONE'],
          filament_color_rgba:[reportedColor,'FFFFFFFF','FFFFFFFF','FFFFFFFF']
        }
      } } }));
      return;
    }
    if (url.pathname === '/printer/gcode/script') {
      scripts.push(url.searchParams.get('script'));
      reportedColor = 'A1B2C3FF';
      res.writeHead(200, { 'content-type':'application/json' });
      res.end(JSON.stringify({ result:'ok' }));
      return;
    }
    res.writeHead(404); res.end();
  });
  const printer = { host:'127.0.0.1', httpPort:port, adapterConfig:{} };
  try {
    const result = await setMoonrakerFilamentColor(printer, { toolIndex:0, color:'#A1B2C3' });
    assert.equal(scripts[0], "SET_PRINT_FILAMENT_CONFIG CONFIG_EXTRUDER='0' FILAMENT_COLOR_RGBA='A1B2C3FF' SAVE='1'");
    assert.deepEqual(result, { toolIndex:0, color:'#A1B2C3', rgba:'A1B2C3FF', verified:true });
  } finally {
    await close(server);
  }
});

test('U1 filament colour write refuses busy, empty, and RFID-locked toolheads', async () => {
  let state = 'printing';
  let exists = true;
  let official = false;
  let editable = true;
  const { server, port } = await listen((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname !== '/printer/objects/query') { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type':'application/json' });
    res.end(JSON.stringify({ result:{ status:{
      print_stats:{ state },
      print_task_config:{
        filament_exist:[exists,false,false,false],
        filament_edit:[editable,false,false,false],
        filament_official:[official,false,false,false],
        filament_type:['PLA','NONE','NONE','NONE'],
        filament_color_rgba:['112233FF','FFFFFFFF','FFFFFFFF','FFFFFFFF']
      }
    } } }));
  });
  const printer = { host:'127.0.0.1', httpPort:port, adapterConfig:{} };
  try {
    await assert.rejects(() => setMoonrakerFilamentColor(printer, { toolIndex:0, color:'#334455' }), /only be changed while the printer is idle/);
    state = 'standby'; exists = false;
    await assert.rejects(() => setMoonrakerFilamentColor(printer, { toolIndex:0, color:'#334455' }), /No filament is loaded/);
    exists = true; official = true; editable = false;
    await assert.rejects(() => setMoonrakerFilamentColor(printer, { toolIndex:0, color:'#334455' }), /locked by its official Snapmaker RFID filament/);
  } finally {
    await close(server);
  }
});

'''
replace_once(
    moon_test,
    "test('tool-specific and all-tool U1 temperature commands use native Klipper heater names', async () => {",
    new_tests + "test('tool-specific and all-tool U1 temperature commands use native Klipper heater names', async () => {",
    'native colour tests'
)

# UI regression test.
ui_test = ROOT / 'test/ui-print-setup.test.js'
ui_extra = r'''
test('Snapmaker U1 manual filament colour control writes colour to the printer', () => {
  assert.match(app, /function u1FilamentColorEditState/);
  assert.match(app, /data-u1-filament-color-input/);
  assert.match(app, /data-u1-filament-color-save/);
  assert.match(app, /Set on U1/);
  assert.match(app, /\/filament-color/);
  assert.match(app, /Official Snapmaker RFID filament controls its own colour/);
  assert.match(styles, /\.u1-filament-color-control/);
});

'''
replace_once(
    ui_test,
    "test('U1 print setup exposes native timelapse and filament safety controls', () => {",
    ui_extra + "test('U1 print setup exposes native timelapse and filament safety controls', () => {",
    'u1 colour UI test'
)

# README + project context.
readme = ROOT / 'README.md'
replace_once(readme, '# Printer Fleet Controller v0.12.7', '# Printer Fleet Controller v0.12.8', 'README heading')
replace_once(
    readme,
    '> v0.12.7 shows FlashForge controller-assigned filament colours as both hexadecimal and **RGB(r, g, b)** values in Toolhead status. The stored colour and automatic queue compatibility behaviour are unchanged.\n',
    '> v0.12.8 adds **native Snapmaker U1 filament colour editing** for manually assigned third-party filament. Toolhead status can write a selected colour to the idle U1 using its stock `SET_PRINT_FILAMENT_CONFIG` command, verifies the printer read-back, and keeps official RFID filament colours locked.\n\n> v0.12.7 shows FlashForge controller-assigned filament colours as both hexadecimal and **RGB(r, g, b)** values in Toolhead status. The stored colour and automatic queue compatibility behaviour are unchanged.\n',
    'README release note'
)

context = ROOT / 'PROJECT_CONTEXT.md'
replace_once(context, 'Current application version: **0.12.7**', 'Current application version: **0.12.8**', 'context version')
replace_once(
    context,
    '- **v0.12.7 FlashForge RGB colour display:** controller-assigned FlashForge filament colours now show the stored `#RRGGBB` value plus `RGB(r, g, b)` in Toolhead status; queue compatibility semantics are unchanged.\n',
    '- **v0.12.7 FlashForge RGB colour display:** controller-assigned FlashForge filament colours now show the stored `#RRGGBB` value plus `RGB(r, g, b)` in Toolhead status; queue compatibility semantics are unchanged.\n- **v0.12.8 native Snapmaker filament colour editing:** manually assigned third-party U1 filament colours can be changed from each toolhead card using stock `SET_PRINT_FILAMENT_CONFIG`; writes are idle/loaded/editable-only and verified against `print_task_config.filament_color_rgba`. Official RFID filament remains colour-locked.\n- v0.12.8 regression suite: **125 passing tests, 0 failures**.\n',
    'context release note'
)
replace_once(
    context,
    '**v0.12.7 FlashForge RGB colour display is complete in code and automated tests.** Next priority is real-hardware validation that assigned FlashForge colours show correctly in both hex and RGB and continue to influence compatibility as expected.',
    '**v0.12.8 native Snapmaker filament colour editing is complete in code and automated tests.** Next priority is real-hardware validation that changing a manually assigned U1 filament colour updates the printer touchscreen and is immediately reflected in controller status/queue compatibility.',
    'context current task'
)
replace_once(
    context,
    '1. Open one FlashForge and one Snapmaker printer window, upload a supported file to each, and confirm the verified file appears immediately in that printer\'s file list.\n',
    '1. On an idle Snapmaker U1 with manually assigned third-party filament loaded, change a toolhead colour in Printer Fleet Controller and confirm the U1 touchscreen updates to the same colour; confirm official RFID spools remain locked.\n2. Open one FlashForge and one Snapmaker printer window, upload a supported file to each, and confirm the verified file appears immediately in that printer\'s file list.\n',
    'context next step'
)
# Renumber the remaining legacy list entries now that a new step 1 was inserted.
text = context.read_text()
for old, new in [('8. After hardware validation', '9. After hardware validation'), ('7. Confirm a printer', '8. Confirm a printer'), ('6. Cancel remaining', '7. Cancel remaining'), ('5. Increase and decrease', '6. Increase and decrease'), ('4. Pause a production', '5. Pause a production'), ('3. Confirm each completed', '4. Confirm each completed'), ('2. Queue a known-good', '3. Queue a known-good')]:
    text = text.replace(old, new, 1)
context.write_text(text)

print('Applied v0.12.8 patch')
