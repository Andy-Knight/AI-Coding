from pathlib import Path
import json

ROOT = Path('print-farm-controller')

def replace_once(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected one match, got {text.count(old)} for {old[:90]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

# Generic capabilities: native project files may require a user mapping/review step.
replace_once('src/adapters/printer-adapter.js',
'''  nativeMultiMaterialWorkflow: false,\n  flowCalibrationBeforePrint: false,''',
'''  nativeMultiMaterialWorkflow: false,\n  projectFileMappingReview: false,\n  flowCalibrationBeforePrint: false,''')

replace_once('src/adapters/bambu-lab-adapter.js',
'''    nativeMultiMaterialWorkflow:true,\n    flowCalibrationBeforePrint:true,''',
'''    nativeMultiMaterialWorkflow:true,\n    projectFileMappingReview:true,\n    flowCalibrationBeforePrint:true,''')
replace_once('src/adapters/bambu-lab-adapter.js',
'''    nativeMultiMaterialWorkflow:true, flowCalibrationBeforePrint:true, timeLapseBeforePrint:true,''',
'''    nativeMultiMaterialWorkflow:true, projectFileMappingReview:true, flowCalibrationBeforePrint:true, timeLapseBeforePrint:true,''')

# Queue compatibility: native AMS workflows are supported but not started unattended until explicit mapping exists.
replace_once('src/queue-compatibility.js',
'''  if (requiredToolCount > 1 && !capabilities.printToolMapping) {\n    incompatible.push({ code:'insufficient_tool_support', text:`File requires ${requiredToolCount} tools` });\n  }''',
'''  if (requiredToolCount > 1 && !capabilities.printToolMapping && !capabilities.nativeMultiMaterialWorkflow) {\n    incompatible.push({ code:'insufficient_tool_support', text:`File requires ${requiredToolCount} tools` });\n  }''')

replace_once('src/queue-compatibility.js',
'''  if (Number.isFinite(Number(limits.toolCount)) && requiredToolCount > Number(limits.toolCount)) {\n    incompatible.push({ code:'insufficient_tool_count', text:`File requires ${requiredToolCount} tools; printer has ${Number(limits.toolCount)}` });\n  }\n\n  let toolMap = null;''',
'''  // A native material-changing workflow (for example Bambu AMS) can service\n  // multiple slicer tools through the printer's own material system even when it\n  // does not expose U1-style physical-head remapping to the controller. Until the\n  // controller has an explicit native slot map, hold those jobs for review rather\n  // than either rejecting them or starting them unattended.\n  if (requiredToolCount > 1 && capabilities.nativeMultiMaterialWorkflow && !capabilities.printToolMapping) {\n    review.push({ code:'native_material_mapping_review', text:'Multi-material job requires printer-native material/slot mapping review before unattended start' });\n  }\n  if (extension === '.3mf' && capabilities.projectFileMappingReview) {\n    review.push({ code:'bambu_project_mapping_review', text:'Project file requires material/plate mapping review before unattended start' });\n  }\n\n  let toolMap = null;''')

replace_once('src/queue-compatibility.js',
'''    const required = Array.isArray(requirements.logicalTools) ? requirements.logicalTools[0] : null;\n    const physical = Array.isArray(state?.status?.tools) ? state.status.tools[0] : null;''',
'''    const required = Array.isArray(requirements.logicalTools) ? requirements.logicalTools[0] : null;\n    const physicalTools = Array.isArray(state?.status?.tools) ? state.status.tools : [];\n    // Printers with multiple fixed physical heads but no remapping API use the\n    // slicer's logical tool index directly. Single-head printers still use T0.\n    const requiredIndex = Number(required?.index);\n    const physical = Number.isInteger(requiredIndex)\n      ? (physicalTools.find((tool) => Number(tool.index) === requiredIndex) || physicalTools[0])\n      : physicalTools[0];''')

# Browser: populate discovered Bambu model, show manufacturer-appropriate material help/RGB, and explain 3MF AMS limitation.
replace_once('public/app.js',
'''  renderAdapterFields(type, {\n    serialNumber: printer.serialNumber || '',\n    httpPort: printer.httpPort || (type === 'snapmaker-u1' ? 7125 : 8898)\n  });''',
'''  renderAdapterFields(type, {\n    model: printer.model || '',\n    serialNumber: printer.serialNumber || '',\n    httpPort: printer.httpPort || (type === 'snapmaker-u1' ? 7125 : 8898)\n  });''')

replace_once('public/app.js',
'''    const materialHelp = printer.adapterType === 'flashforge-ad5m'\n      ? "Filament type uses the controller's manual designation when set, otherwise the value reported by the FlashForge 5M local /detail API. Installed nozzle size uses the controller nozzle designation when set because the 5M API does not reliably expose it. The 5M API also does not expose U1-style filament colour/RFID metadata or a reliable live filament-presence value."\n      : 'Filament presence comes from each U1 motion sensor. Material and colour use the U1\\'s effective per-tool configuration, including manual assignments for third-party filament; RFID data is used as fallback. Nozzle size and XYZ offset come directly from each physical U1 extruder.';''',
'''    const materialHelp = printer.adapterType === 'flashforge-ad5m'\n      ? "Filament type uses the controller's manual designation when set, otherwise the value reported by the FlashForge 5M local /detail API. Installed nozzle size uses the controller nozzle designation when set because the 5M API does not reliably expose it. The 5M API also does not expose U1-style filament colour/RFID metadata or a reliable live filament-presence value."\n      : printer.adapterType === 'bambu-lab'\n        ? 'Material and colour are read from the Bambu printer/active AMS tray when the LAN status feed exposes them. H2 dual-head temperatures/nozzle state are reported per physical extruder. Native AMS slot mapping is deliberately held for review before unattended multi-material queue starts.'\n        : 'Filament presence comes from each U1 motion sensor. Material and colour use the U1\\'s effective per-tool configuration, including manual assignments for third-party filament; RFID data is used as fallback. Nozzle size and XYZ offset come directly from each physical U1 extruder.';''')

replace_once('public/app.js',
'''          ${['snapmaker-u1','flashforge-ad5m'].includes(printer.adapterType) ? `<small class="material-rgb${filamentRgbText(filament.color) ? '' : ' hidden'}" data-material-rgb="${tool.index}">${escapeHtml(filamentRgbText(filament.color) || '')}</small>` : ''}''',
'''          ${['snapmaker-u1','flashforge-ad5m','bambu-lab'].includes(printer.adapterType) ? `<small class="material-rgb${filamentRgbText(filament.color) ? '' : ' hidden'}" data-material-rgb="${tool.index}">${escapeHtml(filamentRgbText(filament.color) || '')}</small>` : ''}''')

# The two adapter-specific colour rendering tests must follow the expanded
# renderer allowlist as Bambu now uses the same hexadecimal/RGB status line.
ui_test_path = root / 'test/ui-print-setup.test.js'
ui_test_text = ui_test_path.read_text(encoding='utf-8')
old_colour_allowlist = r"/\['snapmaker-u1','flashforge-ad5m'\]\.includes\(printer\.adapterType\)/"
new_colour_allowlist = r"/\['snapmaker-u1','flashforge-ad5m','bambu-lab'\]\.includes\(printer\.adapterType\)/"
if ui_test_text.count(old_colour_allowlist) != 2:
    raise SystemExit('Expected exactly two legacy material colour allowlist assertions')
ui_test_path.write_text(ui_test_text.replace(old_colour_allowlist, new_colour_allowlist), encoding='utf-8')

replace_once('public/app.js',
'''      const preflight = materialPreflightText(printer);\n      const materialCheck = await flashForgeFileMaterialCheck(printer, btn.dataset.printFile);\n      const flashForgePreflight = flashForgeFileMaterialText(materialCheck);\n      if (!confirm(`Start ${btn.dataset.printFile} on ${printer.name}?${preflight ? `\\n\\n${preflight}` : ''}${flashForgePreflight ? `\\n\\n${flashForgePreflight}` : ''}`)) return;''',
'''      const preflight = materialPreflightText(printer);\n      const materialCheck = await flashForgeFileMaterialCheck(printer, btn.dataset.printFile);\n      const flashForgePreflight = flashForgeFileMaterialText(materialCheck);\n      const bambuProjectWarning = printer.adapterType === 'bambu-lab' && /\\.3mf$/i.test(btn.dataset.printFile)\n        ? 'Bambu 3MF direct start currently uses the printer default/external-spool path. AMS multi-material slot mapping is not yet controlled here; use Bambu Studio for multi-material 3MF jobs.'\n        : '';\n      if (!confirm(`Start ${btn.dataset.printFile} on ${printer.name}?${preflight ? `\\n\\n${preflight}` : ''}${flashForgePreflight ? `\\n\\n${flashForgePreflight}` : ''}${bambuProjectWarning ? `\\n\\n${bambuProjectWarning}` : ''}`)) return;''')

# Version.
pkg_path = ROOT / 'package.json'
pkg = json.loads(pkg_path.read_text(encoding='utf-8'))
pkg['version'] = '0.13.0'
pkg_path.write_text(json.dumps(pkg, indent=2) + '\n', encoding='utf-8')

# README release notes and manufacturer list.
replace_once('README.md', '# Printer Fleet Controller v0.12.8', '# Printer Fleet Controller v0.13.0')
replace_once('README.md',
'''> v0.12.8 adds **native Snapmaker U1 filament colour editing**''',
'''> v0.13.0 adds **Bambu Lab P1S, P2S, H2S, H2D and H2C** support through local LAN/Developer Mode. The Bambu adapter uses MQTT-over-TLS for live status/control and implicit FTPS for printer-local file listing, upload and verification; model-specific temperature/tool limits are enforced. P1S uses its native JPEG camera transport, while P2S/H2 cameras use RTSPS when `ffmpeg` is available. Single-material G-code can participate in the automatic compatible-printer queue; multi-material/native AMS workflows and Bambu 3MF project files are deliberately held as **Needs review** until explicit AMS/plate mapping is added.\n\n> v0.12.8 adds **native Snapmaker U1 filament colour editing**''')
replace_once('README.md',
'''- **Snapmaker U1** through its local Moonraker/Klipper API.''',
'''- **Snapmaker U1** through its local Moonraker/Klipper API.\n- **Bambu Lab P1S / P2S / H2S / H2D / H2C** through local LAN/Developer Mode MQTT + FTPS.''')

# Context/handoff.
replace_once('PROJECT_CONTEXT.md', '- Current application version: **0.12.8**', '- Current application version: **0.13.0**')
replace_once('PROJECT_CONTEXT.md',
'''        +-- Snapmaker U1 -> Moonraker / Klipper''',
'''        +-- Snapmaker U1 -> Moonraker / Klipper\n        +-- Bambu Lab P1S/P2S/H2S/H2D/H2C -> LAN MQTT/FTPS''')
replace_once('PROJECT_CONTEXT.md',
'''- Snapmaker U1 support via Moonraker/Klipper, including stock camera integration.''',
'''- Snapmaker U1 support via Moonraker/Klipper, including stock camera integration.\n- Bambu Lab P1S, P2S, H2S, H2D and H2C support via local LAN/Developer Mode MQTT + FTPS, with model-specific limits and camera transports.''')
replace_once('PROJECT_CONTEXT.md',
'''- v0.12.8 regression suite: **125 passing tests, 0 failures**.''',
'''- v0.12.8 regression suite: **125 passing tests, 0 failures**.\n- **v0.13.0 Bambu Lab adapter family:** local MQTT-over-TLS status/control, FTPS printer storage listing/upload/verification, local G-code/3MF start path, job/temperature/fan controls, AMS-active material metadata, SSDP discovery, P1S native JPEG camera and P2S/H2 RTSPS camera via optional `ffmpeg`. Automatic single-material G-code scheduling is enabled when compatibility is known; native multi-material/AMS and Bambu project-file mapping are held for review until an explicit mapping workflow exists.\n- v0.13.0 regression suite: **132 passing tests, 0 failures**.''')

start = (ROOT / 'PROJECT_CONTEXT.md').read_text(encoding='utf-8')
old_section = '''## Current task\n\n**v0.12.8 native Snapmaker filament colour editing is complete in code and automated tests.** Next priority is real-hardware validation that changing a manually assigned U1 filament colour updates the printer touchscreen and is immediately reflected in controller status/queue compatibility.\n\n## Next steps\n\n1. On an idle Snapmaker U1 with manually assigned third-party filament loaded, change a toolhead colour in Printer Fleet Controller and confirm the U1 touchscreen updates to the same colour; confirm official RFID spools remain locked.\n2. Open one FlashForge and one Snapmaker printer window, upload a supported file to each, and confirm the verified file appears immediately in that printer's file list.\n3. Queue a known-good single-tool file with quantity 4 or more and confirm multiple compatible printers receive copies concurrently.\n4. Confirm each completed printer waits for **Bed cleared** before it receives the next copy from the same production batch.\n5. Pause a production batch while copies are active and confirm active prints continue but no new copies start; then resume it.\n6. Increase and decrease the requested quantity while copies are waiting and confirm already-started/finished copies are never removed.\n7. Cancel remaining copies and confirm currently active prints continue while all waiting/preparing copies are cancelled.\n8. Confirm a printer that already has the exact filename reuses its printer-local copy rather than uploading it again.\n9. After hardware validation, consider queue priority / scheduling policy as the next scheduler milestone.'''
new_section = '''## Current task\n\n**v0.13.0 Bambu Lab support is complete in code and automated tests.** Next priority is real-hardware validation on at least one Bambu printer, starting with LAN/Developer Mode authentication, MQTT status/control, FTPS file workflow and the model-specific camera path.\n\n## Next steps\n\n1. Enable LAN/Developer Mode on a Bambu printer, add/discover it, and confirm live status plus pause/resume/cancel and temperature/fan control.\n2. Upload a small `.gcode` from the printer window; confirm FTPS verification and local file-list refresh, then direct-print it.\n3. Queue a known single-material Bambu G-code automatically and confirm material/nozzle compatibility plus the existing bed-clearance interlock.\n4. On P1S, validate the native port-6000 JPEG camera; on P2S/H2, validate RTSPS with `ffmpeg` installed on the controller host.\n5. Validate an H2D/H2C dual-head status feed, especially per-head actual/target temperature, nozzle diameter and logical T0/T1 identity.\n6. Confirm multi-material/AMS and Bambu 3MF automatic jobs stop at **Needs review** rather than starting unattended.\n7. Next Bambu milestone: add explicit AMS slot/plate mapping so reviewed multi-material projects can be scheduled safely.\n8. Continue production-batch hardware validation across mixed manufacturers, then consider queue priority / scheduling policy.'''
if old_section not in start:
    raise SystemExit('PROJECT_CONTEXT current/next section anchor not found')
(ROOT / 'PROJECT_CONTEXT.md').write_text(start.replace(old_section, new_section, 1), encoding='utf-8')

print('Applied v0.13.0 integration patch')
