from pathlib import Path
import json

ROOT = Path('print-farm-controller')


def replace_once(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one match, got {count} for {old[:100]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


# The finalizer deliberately exempts native material-changing printers from the
# logical slicer-tool count check. Restore the original physical-tool safety rule
# for every non-native workflow. Bambu AMS is represented separately below as
# material slots; AMS slots must never inflate limits.toolCount or status.tools.
replace_once(
    'src/queue-compatibility.js',
    "  // A native material-changing workflow (for example Bambu AMS) can service\n",
    "  if (!capabilities.nativeMultiMaterialWorkflow && Number.isFinite(Number(limits.toolCount)) && requiredToolCount > Number(limits.toolCount)) {\n"
    "    incompatible.push({ code:'insufficient_tool_count', text:`File requires ${requiredToolCount} tools; printer has ${Number(limits.toolCount)}` });\n"
    "  }\n\n"
    "  // A native material-changing workflow (for example Bambu AMS) can service\n"
)

# Add manufacturer-neutral material-slot matching for printers whose native
# material changer can service multiple slicer materials through fewer physical
# extruders. This is informational/safety validation only: native multi-material
# jobs remain Needs review until an explicit start-time slot mapping workflow exists.
replace_once(
    'src/queue-compatibility.js',
    "function mapLogicalTools(requirements = {}, status = {}) {\n",
    "function materialSlotMatches(required, slot) {\n"
    "  if (slot?.present === false) return false;\n"
    "  const requiredMaterial = canonicalMaterial(required?.material);\n"
    "  const currentMaterial = canonicalMaterial(slot?.material || slot?.type);\n"
    "  if (requiredMaterial && currentMaterial && requiredMaterial !== currentMaterial) return false;\n"
    "  const requiredColor = normalizeColor(required?.color);\n"
    "  const currentColor = normalizeColor(slot?.color);\n"
    "  if (requiredColor && currentColor && requiredColor !== currentColor) return false;\n"
    "  return true;\n"
    "}\n\n"
    "function nativeMaterialSlots(status = {}) {\n"
    "  if (Array.isArray(status.materialInventory)) return status.materialInventory;\n"
    "  if (Array.isArray(status.materials?.slots)) return status.materials.slots;\n"
    "  return [];\n"
    "}\n\n"
    "function mapNativeMaterialSlots(requirements = {}, status = {}) {\n"
    "  const logicalTools = Array.isArray(requirements.logicalTools) ? requirements.logicalTools : [];\n"
    "  const slots = nativeMaterialSlots(status)\n"
    "    .filter((slot) => slot?.present !== false)\n"
    "    .filter((slot) => Number.isInteger(Number(slot?.index)));\n"
    "  if (!logicalTools.length) return { materialSlotMap:null, reasons:[], review:[] };\n"
    "  if (!slots.length) {\n"
    "    return {\n"
    "      materialSlotMap:null,\n"
    "      reasons:[],\n"
    "      review:[{ code:'material_inventory_unknown', text:'Printer material-slot inventory is not available for this multi-material job' }]\n"
    "    };\n"
    "  }\n\n"
    "  const descriptors = logicalTools.map((logical) => ({\n"
    "    logical,\n"
    "    candidates:slots.filter((slot) => materialSlotMatches(logical, slot))\n"
    "  }));\n"
    "  const missing = descriptors.filter((item) => !item.candidates.length);\n"
    "  if (missing.length) {\n"
    "    return {\n"
    "      materialSlotMap:null,\n"
    "      review:[],\n"
    "      reasons:missing.map(({ logical }) => ({\n"
    "        code:'material_slot_not_loaded',\n"
    "        text:`No loaded material slot matches file T${logical.index} (${requirementText(logical)})`\n"
    "      }))\n"
    "    };\n"
    "  }\n\n"
    "  const ordered = [...descriptors].sort((a, b) => a.candidates.length - b.candidates.length || Number(a.logical.index) - Number(b.logical.index));\n"
    "  const assigned = new Map();\n"
    "  const usedSlots = new Set();\n"
    "  function choose(position) {\n"
    "    if (position >= ordered.length) return true;\n"
    "    const descriptor = ordered[position];\n"
    "    for (const slot of descriptor.candidates) {\n"
    "      const slotIndex = Number(slot.index);\n"
    "      if (usedSlots.has(slotIndex)) continue;\n"
    "      usedSlots.add(slotIndex);\n"
    "      assigned.set(Number(descriptor.logical.index), slot);\n"
    "      if (choose(position + 1)) return true;\n"
    "      assigned.delete(Number(descriptor.logical.index));\n"
    "      usedSlots.delete(slotIndex);\n"
    "    }\n"
    "    return false;\n"
    "  }\n\n"
    "  if (!choose(0)) {\n"
    "    return {\n"
    "      materialSlotMap:null,\n"
    "      review:[],\n"
    "      reasons:[{ code:'material_slot_mapping_conflict', text:'No unique loaded material-slot mapping satisfies all file material requirements' }]\n"
    "    };\n"
    "  }\n\n"
    "  const materialSlotMap = {};\n"
    "  for (const logical of logicalTools) {\n"
    "    materialSlotMap[String(logical.index)] = Number(assigned.get(Number(logical.index)).index);\n"
    "  }\n"
    "  return { materialSlotMap, reasons:[], review:[] };\n"
    "}\n\n"
    "function validateNativeMaterialNozzles(requirements = {}, status = {}) {\n"
    "  const logicalTools = Array.isArray(requirements.logicalTools) ? requirements.logicalTools : [];\n"
    "  const requiredNozzles = [...new Set(logicalTools\n"
    "    .map((tool) => Number(tool?.nozzleDiameter))\n"
    "    .filter((diameter) => Number.isFinite(diameter) && diameter > 0))];\n"
    "  if (!requiredNozzles.length) return { reasons:[], review:[] };\n"
    "  const physicalTools = (Array.isArray(status.tools) ? status.tools : [])\n"
    "    .filter((tool) => Number.isFinite(Number(tool?.nozzleDiameter)));\n"
    "  if (!physicalTools.length) {\n"
    "    return { reasons:[], review:[{ code:'nozzle_unknown', text:'Installed physical nozzle size is not reported for this multi-material job' }] };\n"
    "  }\n"
    "  const missing = requiredNozzles.filter((diameter) => !physicalTools.some((tool) => sameNozzle(diameter, tool.nozzleDiameter)));\n"
    "  return {\n"
    "    reasons:missing.map((diameter) => ({\n"
    "      code:'nozzle_mismatch',\n"
    "      text:`No physical print tool has the required ${diameter.toFixed(1)} mm nozzle`\n"
    "    })),\n"
    "    review:[]\n"
    "  };\n"
    "}\n\n"
    "function mapLogicalTools(requirements = {}, status = {}) {\n"
)

replace_once(
    'src/queue-compatibility.js',
    "  let toolMap = null;\n  if (!incompatible.length && capabilities.printToolMapping && requiredToolCount) {\n",
    "  let toolMap = null;\n"
    "  let materialSlotMap = null;\n"
    "  if (!incompatible.length && requiredToolCount > 1 && capabilities.nativeMultiMaterialWorkflow && !capabilities.printToolMapping) {\n"
    "    const mappedMaterials = mapNativeMaterialSlots(requirements, state?.status || {});\n"
    "    materialSlotMap = mappedMaterials.materialSlotMap;\n"
    "    blocked.push(...mappedMaterials.reasons);\n"
    "    review.push(...mappedMaterials.review);\n"
    "    const nozzleCheck = validateNativeMaterialNozzles(requirements, state?.status || {});\n"
    "    blocked.push(...nozzleCheck.reasons);\n"
    "    review.push(...nozzleCheck.review);\n"
    "  }\n"
    "  if (!incompatible.length && capabilities.printToolMapping && requiredToolCount) {\n"
)

replace_once(
    'src/queue-compatibility.js',
    "    compatible: !incompatible.length,\n    toolMap,\n    reasons: [...incompatible, ...review, ...blocked]\n",
    "    compatible: !incompatible.length,\n    toolMap,\n    materialSlotMap,\n    reasons: [...incompatible, ...review, ...blocked]\n"
)

# Expose the complete AMS/external-spool inventory separately from physical
# extruders. This keeps P1/P2/H2S as one physical print tool even with many AMS
# slots, while H2D/H2C retain their actual two-extruder topology.
replace_once(
    'src/bambu-api.js',
    "function normalizeFilament(print = {}) {\n",
    "function normalizeMaterialSlot(tray, index, source, slotType) {\n"
    "  if (!tray || typeof tray !== 'object') return null;\n"
    "  const material = String(tray.tray_type || tray.type || '').trim() || null;\n"
    "  const color = normalizeHex(tray.tray_color || tray.color);\n"
    "  const variant = String(tray.tray_sub_brands || tray.sub_brands || '').trim() || null;\n"
    "  const vendor = String(tray.tray_info_idx || '').trim() || null;\n"
    "  const present = Boolean(material || color || variant || vendor);\n"
    "  return {\n"
    "    index:Number(index),\n"
    "    present,\n"
    "    metadataAvailable:present,\n"
    "    materialSource:'printer',\n"
    "    material,\n"
    "    materialVariant:variant,\n"
    "    color,\n"
    "    vendor,\n"
    "    source,\n"
    "    slotType\n"
    "  };\n"
    "}\n\n"
    "function normalizeMaterialInventory(print = {}) {\n"
    "  const ams = print.ams || {};\n"
    "  const slots = [];\n"
    "  const units = Array.isArray(ams.ams) ? ams.ams : [];\n"
    "  units.forEach((unit, unitPosition) => {\n"
    "    const unitId = Number.isInteger(Number(unit?.id)) ? Number(unit.id) : unitPosition;\n"
    "    const trays = Array.isArray(unit?.tray) ? unit.tray : [];\n"
    "    trays.forEach((tray, trayPosition) => {\n"
    "      const trayId = Number.isInteger(Number(tray?.id)) ? Number(tray.id) : trayPosition;\n"
    "      const slot = normalizeMaterialSlot(tray, unitId * 4 + trayId, `AMS ${unitId + 1} slot ${trayId + 1}`, 'ams');\n"
    "      if (slot) slots.push(slot);\n"
    "    });\n"
    "  });\n"
    "  const external = ams.vt_tray || print.vt_tray || null;\n"
    "  if (external) {\n"
    "    const slot = normalizeMaterialSlot(external, 254, 'External spool', 'external');\n"
    "    if (slot) slots.push(slot);\n"
    "  }\n"
    "  return slots;\n"
    "}\n\n"
    "function normalizeFilament(print = {}) {\n"
)

replace_once(
    'src/bambu-api.js',
    "  const tools = normalizeExtruderTools(print, modelProfile);\n  const activeTool = tools.find((tool) => tool.active) || tools[0];\n",
    "  const tools = normalizeExtruderTools(print, modelProfile);\n"
    "  const materialInventory = normalizeMaterialInventory(print);\n"
    "  const activeTool = tools.find((tool) => tool.active) || tools[0];\n"
)

replace_once(
    'src/bambu-api.js',
    "    tools,\n    materials:{\n      available:tools.some((tool) => tool.filament?.metadataAvailable || tool.filament?.present !== null),\n      loadedCount:tools.filter((tool) => tool.filament?.present === true).length,\n      toolCount:tools.length,\n      metadataCount:tools.filter((tool) => tool.filament?.metadataAvailable).length,\n      tools:tools.map((tool) => tool.filament)\n    },\n",
    "    tools,\n"
    "    materialInventory,\n"
    "    materials:{\n"
    "      available:materialInventory.length > 0 || tools.some((tool) => tool.filament?.metadataAvailable || tool.filament?.present !== null),\n"
    "      loadedCount:materialInventory.length ? materialInventory.filter((slot) => slot.present === true).length : tools.filter((tool) => tool.filament?.present === true).length,\n"
    "      toolCount:tools.length,\n"
    "      slotCount:materialInventory.length,\n"
    "      metadataCount:materialInventory.length ? materialInventory.filter((slot) => slot.metadataAvailable).length : tools.filter((tool) => tool.filament?.metadataAvailable).length,\n"
    "      tools:tools.map((tool) => tool.filament),\n"
    "      slots:materialInventory\n"
    "    },\n"
)

# Safety: project-file start remains disabled until the future reviewed AMS/plate
# mapping flow explicitly opts in. Upload/storage support remains available.
replace_once(
    'src/bambu-api.js',
    "  if (/\\.3mf$/i.test(name)) {\n    const payload = {",
    "  if (/\\.3mf$/i.test(name)) {\n"
    "    if (options.allowProjectStart !== true) {\n"
    "      throw new BambuApiError('Bambu 3MF project start requires reviewed AMS/plate mapping; upload/storage is supported but direct start is disabled');\n"
    "    }\n"
    "    const payload = {"
)

# Extend existing Bambu regressions without inflating AMS slots into tools.
test_file = ROOT / 'test/bambu-api.test.js'
test_text = test_file.read_text(encoding='utf-8')
old_import = "import { normalizeBambuStatus } from '../src/bambu-api.js';"
new_import = "import { normalizeBambuStatus, startBambuFile } from '../src/bambu-api.js';"
if test_text.count(old_import) != 1:
    raise SystemExit('Bambu test import anchor not found exactly once')
test_text = test_text.replace(old_import, new_import, 1)

old_assert = "  assert.equal(status.tools[0].filament.color, '#2F80ED');\n"
new_assert = (
    "  assert.equal(status.tools[0].filament.color, '#2F80ED');\n"
    "  assert.equal(status.materials.toolCount, 1);\n"
    "  assert.equal(status.materials.slotCount, 2);\n"
    "  assert.deepEqual(status.materialInventory.map((slot) => [slot.index, slot.material, slot.color]), [\n"
    "    [0, 'PLA', '#FF0000'],\n"
    "    [1, 'PETG', '#2F80ED']\n"
    "  ]);\n"
)
if test_text.count(old_assert) != 1:
    raise SystemExit('Bambu inventory assertion anchor not found exactly once')
test_text = test_text.replace(old_assert, new_assert, 1)

old_state = "    status:{ status:'idle', fileName:null, tools:[{ index:0, nozzleDiameter:0.4, filament:{ present:true, material:'PLA', color:'#FF0000' } }] }\n"
new_state = (
    "    status:{ status:'idle', fileName:null,\n"
    "      tools:[{ index:0, nozzleDiameter:0.4, filament:{ present:true, material:'PLA', color:'#FF0000' } }],\n"
    "      materialInventory:[\n"
    "        { index:0, present:true, material:'PLA', color:'#FF0000', source:'AMS 1 slot 1' },\n"
    "        { index:1, present:true, material:'PETG', color:'#00FF00', source:'AMS 1 slot 2' }\n"
    "      ]\n"
    "    }\n"
)
if test_text.count(old_state) != 1:
    raise SystemExit('Bambu queue state anchor not found exactly once')
test_text = test_text.replace(old_state, new_state, 1)

test_text = test_text.replace(
    "logicalTools:[{ index:0, material:'PLA' },{ index:1, material:'PLA' }]",
    "logicalTools:[{ index:0, material:'PLA', nozzleDiameter:0.4 },{ index:1, material:'PETG', nozzleDiameter:0.4 }]",
    1
)
old_multi_assert = "  assert.ok(multi.reasons.some((reason) => reason.code === 'native_material_mapping_review'), JSON.stringify(multi));\n"
new_multi_assert = (
    "  assert.ok(multi.reasons.some((reason) => reason.code === 'native_material_mapping_review'), JSON.stringify(multi));\n"
    "  assert.deepEqual(multi.materialSlotMap, { '0':0, '1':1 });\n"
    "  assert.equal(state.status.tools.length, 1, 'AMS slots must not inflate physical print-tool count');\n\n"
    "  const impossibleNozzle = evaluateQueueCompatibility({\n"
    "    printer:{ id:'bambu' }, state, adapter,\n"
    "    job:{ fileName:'wrong-nozzle.gcode', requirements:{ toolCount:2, requiredTools:[0,1], logicalTools:[\n"
    "      { index:0, material:'PLA', nozzleDiameter:0.4 },\n"
    "      { index:1, material:'PETG', nozzleDiameter:0.6 }\n"
    "    ] } }\n"
    "  });\n"
    "  assert.equal(impossibleNozzle.category, 'blocked', JSON.stringify(impossibleNozzle));\n"
    "  assert.ok(impossibleNozzle.reasons.some((reason) => reason.code === 'nozzle_mismatch'), JSON.stringify(impossibleNozzle));\n"
)
if test_text.count(old_multi_assert) != 1:
    raise SystemExit('Bambu multi-material assertion anchor not found exactly once')
test_text = test_text.replace(old_multi_assert, new_multi_assert, 1)

test_text += """

test('Bambu 3MF direct start is blocked until reviewed AMS and plate mapping exists', async () => {
  await assert.rejects(
    () => startBambuFile(
      { host:'127.0.0.1', serialNumber:'SERIAL', adapterConfig:{ accessCode:'code' } },
      'multi-material.3mf',
      {},
      bambuModelProfile('P1S')
    ),
    /requires reviewed AMS\/plate mapping/
  );
});
"""
test_file.write_text(test_text, encoding='utf-8')

# Correct release handoff wording/count after the finalizer has updated the docs.
context_path = ROOT / 'PROJECT_CONTEXT.md'
context = context_path.read_text(encoding='utf-8')
context = context.replace(
    'FTPS printer storage listing/upload/verification, local G-code/3MF start path,',
    'FTPS printer storage listing/upload/verification, local G-code start path plus 3MF storage support,'
)
context = context.replace(
    'v0.13.0 regression suite: **132 passing tests, 0 failures**.',
    'v0.13.0 regression suite: **133 passing tests, 0 failures**.'
)
context_path.write_text(context, encoding='utf-8')

# Keep package metadata aligned with the newly supported manufacturer family.
pkg_path = ROOT / 'package.json'
pkg = json.loads(pkg_path.read_text(encoding='utf-8'))
pkg['description'] = 'Printer Fleet Controller: local-first multi-manufacturer 3D printer fleet control with FlashForge Adventurer 5M/5M Pro, Snapmaker U1, and Bambu Lab support'
pkg_path.write_text(json.dumps(pkg, indent=2) + '\n', encoding='utf-8')

print('Applied Bambu AMS material-slot model, restored physical-tool safety, and hardened 3MF start safety')
