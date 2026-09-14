import path from 'node:path';
import { canonicalMaterial } from './file-material-metadata.js';

const ACTIVE_STATES = new Set(['printing', 'working', 'building_from_sd', 'pause', 'paused']);

function normState(value) {
  return String(value || '').trim().toLowerCase();
}

function isBusy(status = {}) {
  const state = normState(status.status);
  if (status.fileName) return true;
  if (ACTIVE_STATES.has(state)) return true;
  if (state === 'heating' && status.fileName) return true;
  return !['', 'idle', 'ready', 'standby', 'complete', 'completed'].includes(state);
}

function normalizeColor(value) {
  const text = String(value || '').trim().replace(/^0x/i, '').replace(/^#/, '').toUpperCase();
  if (/^[0-9A-F]{8}$/.test(text)) return `#${text.slice(2)}`;
  if (/^[0-9A-F]{6}$/.test(text)) return `#${text}`;
  return null;
}

function sameNozzle(a, b) {
  const left = Number(a);
  const right = Number(b);
  return Number.isFinite(left) && Number.isFinite(right) && Math.abs(left - right) < 0.001;
}

function requirementText(tool) {
  const parts = [];
  if (tool.material) parts.push(String(tool.material));
  if (tool.color) parts.push(String(tool.color));
  if (tool.nozzleDiameter != null) parts.push(`${Number(tool.nozzleDiameter).toFixed(1)} mm nozzle`);
  return parts.length ? parts.join(', ') : 'loaded filament';
}

function toolMatches(required, physical) {
  const filament = physical?.filament || {};
  if (filament.present === false) return false;
  if (required.nozzleDiameter != null && Number.isFinite(Number(physical?.nozzleDiameter)) && !sameNozzle(required.nozzleDiameter, physical.nozzleDiameter)) return false;
  const requiredMaterial = canonicalMaterial(required.material);
  const currentMaterial = canonicalMaterial(filament.material);
  if (requiredMaterial && currentMaterial && requiredMaterial !== currentMaterial) return false;
  const requiredColor = normalizeColor(required.color);
  const currentColor = normalizeColor(filament.color);
  if (requiredColor && currentColor && requiredColor !== currentColor) return false;
  return true;
}

function materialSlotMatches(required, slot) {
  if (slot?.present === false) return false;
  const requiredMaterial = canonicalMaterial(required?.material);
  const currentMaterial = canonicalMaterial(slot?.material || slot?.type);
  if (requiredMaterial && currentMaterial && requiredMaterial !== currentMaterial) return false;
  const requiredColor = normalizeColor(required?.color);
  const currentColor = normalizeColor(slot?.color);
  if (requiredColor && currentColor && requiredColor !== currentColor) return false;
  return true;
}

function nativeMaterialSlots(status = {}) {
  if (Array.isArray(status.materialInventory)) return status.materialInventory;
  if (Array.isArray(status.materials?.slots)) return status.materials.slots;
  return [];
}

function mapNativeMaterialSlots(requirements = {}, status = {}) {
  const logicalTools = Array.isArray(requirements.logicalTools) ? requirements.logicalTools : [];
  const slots = nativeMaterialSlots(status)
    .filter((slot) => slot?.present !== false)
    .filter((slot) => Number.isInteger(Number(slot?.index)));
  if (!logicalTools.length) return { materialSlotMap:null, reasons:[], review:[] };
  if (!slots.length) {
    return {
      materialSlotMap:null,
      reasons:[],
      review:[{ code:'material_inventory_unknown', text:'Printer material-slot inventory is not available for this multi-material job' }]
    };
  }

  const descriptors = logicalTools.map((logical) => ({
    logical,
    candidates:slots.filter((slot) => materialSlotMatches(logical, slot))
  }));
  const missing = descriptors.filter((item) => !item.candidates.length);
  if (missing.length) {
    return {
      materialSlotMap:null,
      review:[],
      reasons:missing.map(({ logical }) => ({
        code:'material_slot_not_loaded',
        text:`No loaded material slot matches file T${logical.index} (${requirementText(logical)})`
      }))
    };
  }

  const ordered = [...descriptors].sort((a, b) => a.candidates.length - b.candidates.length || Number(a.logical.index) - Number(b.logical.index));
  const assigned = new Map();
  const usedSlots = new Set();
  function choose(position) {
    if (position >= ordered.length) return true;
    const descriptor = ordered[position];
    for (const slot of descriptor.candidates) {
      const slotIndex = Number(slot.index);
      if (usedSlots.has(slotIndex)) continue;
      usedSlots.add(slotIndex);
      assigned.set(Number(descriptor.logical.index), slot);
      if (choose(position + 1)) return true;
      assigned.delete(Number(descriptor.logical.index));
      usedSlots.delete(slotIndex);
    }
    return false;
  }

  if (!choose(0)) {
    return {
      materialSlotMap:null,
      review:[],
      reasons:[{ code:'material_slot_mapping_conflict', text:'No unique loaded material-slot mapping satisfies all file material requirements' }]
    };
  }

  const materialSlotMap = {};
  for (const logical of logicalTools) {
    materialSlotMap[String(logical.index)] = Number(assigned.get(Number(logical.index)).index);
  }
  return { materialSlotMap, reasons:[], review:[] };
}

function validateNativeMaterialNozzles(requirements = {}, status = {}) {
  const logicalTools = Array.isArray(requirements.logicalTools) ? requirements.logicalTools : [];
  const requiredNozzles = [...new Set(logicalTools
    .map((tool) => Number(tool?.nozzleDiameter))
    .filter((diameter) => Number.isFinite(diameter) && diameter > 0))];
  if (!requiredNozzles.length) return { reasons:[], review:[] };
  const physicalTools = (Array.isArray(status.tools) ? status.tools : [])
    .filter((tool) => Number.isFinite(Number(tool?.nozzleDiameter)));
  if (!physicalTools.length) {
    return { reasons:[], review:[{ code:'nozzle_unknown', text:'Installed physical nozzle size is not reported for this multi-material job' }] };
  }
  const missing = requiredNozzles.filter((diameter) => !physicalTools.some((tool) => sameNozzle(diameter, tool.nozzleDiameter)));
  return {
    reasons:missing.map((diameter) => ({
      code:'nozzle_mismatch',
      text:`No physical print tool has the required ${diameter.toFixed(1)} mm nozzle`
    })),
    review:[]
  };
}

function mapLogicalTools(requirements = {}, status = {}) {
  const logicalTools = Array.isArray(requirements.logicalTools) ? requirements.logicalTools : [];
  const physicalTools = Array.isArray(status.tools) ? status.tools : [];
  if (!logicalTools.length) return { ok:true, toolMap:null, reasons:[], review:[] };

  const descriptors = logicalTools.map((logical) => ({
    logical,
    candidates:physicalTools
      .filter((tool) => Number.isInteger(Number(tool.index)))
      .filter((tool) => toolMatches(logical, tool))
  }));
  const missing = descriptors.filter((item) => !item.candidates.length);
  if (missing.length) {
    return {
      ok:false,
      toolMap:null,
      review:[],
      reasons:missing.map(({ logical }) => ({
        code:'tool_not_loaded',
        text:`No loaded tool matches file T${logical.index} (${requirementText(logical)})`
      }))
    };
  }

  // Assign the most constrained logical tools first so a broad requirement
  // cannot consume the only physical head that satisfies a later exact match.
  const ordered = [...descriptors].sort((a, b) => a.candidates.length - b.candidates.length || Number(a.logical.index) - Number(b.logical.index));
  const assigned = new Map();
  const usedPhysical = new Set();
  function choose(position) {
    if (position >= ordered.length) return true;
    const descriptor = ordered[position];
    for (const physical of descriptor.candidates) {
      const physicalIndex = Number(physical.index);
      if (usedPhysical.has(physicalIndex)) continue;
      usedPhysical.add(physicalIndex);
      assigned.set(Number(descriptor.logical.index), physical);
      if (choose(position + 1)) return true;
      assigned.delete(Number(descriptor.logical.index));
      usedPhysical.delete(physicalIndex);
    }
    return false;
  }

  if (!choose(0)) {
    return {
      ok:false,
      toolMap:null,
      review:[],
      reasons:[{ code:'tool_mapping_conflict', text:'No unique physical tool mapping satisfies all file tool requirements' }]
    };
  }

  const toolMap = {};
  const review = [];
  for (const logical of logicalTools) {
    const selected = assigned.get(Number(logical.index));
    toolMap[String(logical.index)] = Number(selected.index);
    if (logical.material && !canonicalMaterial(selected.filament?.material)) {
      review.push({ code:'material_unknown', text:`Physical T${selected.index} material is unknown for file T${logical.index} (${logical.material})` });
    }
    if (logical.nozzleDiameter != null && !Number.isFinite(Number(selected.nozzleDiameter))) {
      review.push({ code:'nozzle_unknown', text:`Physical T${selected.index} nozzle size is not reported for file T${logical.index} (${Number(logical.nozzleDiameter).toFixed(1)} mm)` });
    }
  }
  return { ok:review.length === 0, toolMap, reasons:[], review };
}

export function evaluateQueueCompatibility({ job, printer, state, adapter, bedClearanceRequired = false, reserved = false } = {}) {
  const incompatible = [];
  const blocked = [];
  const review = [];
  const requirements = job?.requirements || job?.stagedFile?.requirements || {};
  const capabilities = adapter?.capabilities || state?.capabilities || {};
  const limits = adapter?.limits || state?.limits || {};

  if (!capabilities.fileUpload || !capabilities.localFiles || !capabilities.printLocalFile) {
    incompatible.push({ code:'missing_file_workflow', text:'Printer does not support verified controller file upload and local print start' });
  }
  const extension = path.extname(String(job?.fileName || '')).toLowerCase();
  const acceptedExtensions = Array.isArray(adapter?.uploadExtensions) ? adapter.uploadExtensions.map((item) => String(item).toLowerCase()) : [];
  if (extension && acceptedExtensions.length && !acceptedExtensions.includes(extension)) {
    incompatible.push({ code:'unsupported_file_type', text:`Printer does not support ${extension} uploads` });
  }

  const requiredTools = Array.isArray(requirements.requiredTools) ? requirements.requiredTools : [];
  const requiredToolCount = Number(requirements.toolCount || requiredTools.length || 0);
  if (requiredToolCount > 1 && !capabilities.printToolMapping && !capabilities.nativeMultiMaterialWorkflow) {
    incompatible.push({ code:'insufficient_tool_support', text:`File requires ${requiredToolCount} tools` });
  }
  if (!capabilities.nativeMultiMaterialWorkflow && Number.isFinite(Number(limits.toolCount)) && requiredToolCount > Number(limits.toolCount)) {
    incompatible.push({ code:'insufficient_tool_count', text:`File requires ${requiredToolCount} tools; printer has ${Number(limits.toolCount)}` });
  }

  // A native material-changing workflow (for example Bambu AMS) can service
  // multiple slicer tools through the printer's own material system even when it
  // does not expose U1-style physical-head remapping to the controller. Until the
  // controller has an explicit native slot map, hold those jobs for review rather
  // than either rejecting them or starting them unattended.
  if (requiredToolCount > 1 && capabilities.nativeMultiMaterialWorkflow && !capabilities.printToolMapping) {
    review.push({ code:'native_material_mapping_review', text:'Multi-material job requires printer-native material/slot mapping review before unattended start' });
  }
  if (extension === '.3mf' && capabilities.projectFileMappingReview) {
    review.push({ code:'bambu_project_mapping_review', text:'Project file requires material/plate mapping review before unattended start' });
  }

  let toolMap = null;
  let materialSlotMap = null;
  if (!incompatible.length && requiredToolCount > 1 && capabilities.nativeMultiMaterialWorkflow && !capabilities.printToolMapping) {
    const mappedMaterials = mapNativeMaterialSlots(requirements, state?.status || {});
    materialSlotMap = mappedMaterials.materialSlotMap;
    blocked.push(...mappedMaterials.reasons);
    review.push(...mappedMaterials.review);
    const nozzleCheck = validateNativeMaterialNozzles(requirements, state?.status || {});
    blocked.push(...nozzleCheck.reasons);
    review.push(...nozzleCheck.review);
  }
  if (!incompatible.length && capabilities.printToolMapping && requiredToolCount) {
    if (requirements.usageReliable === false && requiredToolCount > 1) {
      review.push({ code:'unreliable_tool_usage', text:'File tool usage could not be determined reliably for unattended multi-tool scheduling' });
    } else {
      const mapped = mapLogicalTools(requirements, state?.status || {});
      toolMap = mapped.toolMap;
      blocked.push(...mapped.reasons);
      review.push(...mapped.review);
    }
  } else if (!incompatible.length && requiredToolCount === 1) {
    const required = Array.isArray(requirements.logicalTools) ? requirements.logicalTools[0] : null;
    const physicalTools = Array.isArray(state?.status?.tools) ? state.status.tools : [];
    // Printers with multiple fixed physical heads but no remapping API use the
    // slicer's logical tool index directly. Single-head printers still use T0.
    const requiredIndex = Number(required?.index);
    const physical = Number.isInteger(requiredIndex)
      ? (physicalTools.find((tool) => Number(tool.index) === requiredIndex) || physicalTools[0])
      : physicalTools[0];
    if (required && physical) {
      if (physical.filament?.present === false) blocked.push({ code:'filament_absent', text:'Filament is not loaded' });
      const requiredMaterial = canonicalMaterial(required.material);
      const currentMaterial = canonicalMaterial(physical.filament?.material);
      if (requiredMaterial && !currentMaterial) {
        review.push({ code:'material_unknown', text:`File requires ${required.material}, but loaded material is not known` });
      } else if (requiredMaterial && currentMaterial && requiredMaterial !== currentMaterial) {
        blocked.push({ code:'material_mismatch', text:`Loaded material ${physical.filament.material} does not match required ${required.material}` });
      }
      if (required.nozzleDiameter != null && !Number.isFinite(Number(physical.nozzleDiameter))) {
        review.push({ code:'nozzle_unknown', text:`File requires a ${Number(required.nozzleDiameter).toFixed(1)} mm nozzle, but installed nozzle size is not reported` });
      } else if (required.nozzleDiameter != null && Number.isFinite(Number(physical.nozzleDiameter)) && !sameNozzle(required.nozzleDiameter, physical.nozzleDiameter)) {
        blocked.push({ code:'nozzle_mismatch', text:`Installed nozzle ${Number(physical.nozzleDiameter).toFixed(1)} mm does not match required ${Number(required.nozzleDiameter).toFixed(1)} mm` });
      }
      const requiredColor = normalizeColor(required.color);
      const currentColor = normalizeColor(physical.filament?.color);
      if (requiredColor && currentColor && requiredColor !== currentColor) {
        blocked.push({ code:'color_mismatch', text:`Loaded filament colour ${currentColor} does not match required ${requiredColor}` });
      }
    }
  }

  if (!state?.online) blocked.push({ code:'offline', text:state?.error || 'Printer is offline' });
  else if (isBusy(state.status || {})) blocked.push({ code:'busy', text:'Printer is not idle' });
  if (bedClearanceRequired) blocked.push({ code:'bed_not_cleared', text:'Bed not cleared' });
  if (reserved) blocked.push({ code:'reserved', text:'Printer is reserved by another queued job' });

  const category = incompatible.length ? 'incompatible' : blocked.length ? 'blocked' : review.length ? 'needs_review' : 'ready';
  return {
    printerId: printer?.id || state?.id || null,
    printerName: state?.name || printer?.name || printer?.id || state?.id || 'Printer',
    category,
    ready: category === 'ready',
    compatible: !incompatible.length,
    toolMap,
    materialSlotMap,
    reasons: [...incompatible, ...review, ...blocked]
  };
}

export const queueCompatibilityHelpers = { isBusy, mapLogicalTools, normalizeColor, sameNozzle };
