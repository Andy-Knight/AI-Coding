import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeBambuStatus, startBambuFile } from '../src/bambu-api.js';
import { parseBambuSsdpPacket } from '../src/bambu-discovery.js';
import { createBambuCameraSource, P1SnapshotSource, RtspsSnapshotSource } from '../src/bambu-camera.js';
import { bambuModelProfile, prepareBambuConfig } from '../src/adapters/bambu-lab-adapter.js';
import { getPrinterAdapter, listAdapterDefinitions } from '../src/adapters/adapter-registry.js';
import { evaluateQueueCompatibility } from '../src/queue-compatibility.js';
import { publicPrinter } from '../src/store.js';

function packedTemp(actual, target) {
  return ((target & 0xFFFF) << 16) | (actual & 0xFFFF);
}

test('normalizes Bambu P1S status with active AMS material, temperatures and progress', () => {
  const status = normalizeBambuStatus({ print:{
    gcode_state:'RUNNING', subtask_name:'farm-part', mc_percent:42, mc_remaining_time:17,
    layer_num:21, total_layer_num:50, nozzle_temper:221.4, nozzle_target_temper:220,
    bed_temper:61.2, bed_target_temper:60, chamber_temper:37.5,
    cooling_fan_speed:128, big_fan1_speed:64, big_fan2_speed:255,
    nozzle_diameter:'0.4',
    ams:{ tray_now:1, ams:[{ id:'0', tray:[
      { id:'0', tray_type:'PLA', tray_color:'FF0000FF' },
      { id:'1', tray_type:'PETG', tray_sub_brands:'Basic', tray_color:'2F80EDFF' }
    ] }] }
  } }, bambuModelProfile('P1S'));

  assert.equal(status.status, 'printing');
  assert.equal(status.fileName, 'farm-part');
  assert.equal(status.progress, 42);
  assert.equal(status.currentLayer, 21);
  assert.equal(status.totalLayers, 50);
  assert.equal(status.remainingSeconds, 1020);
  assert.equal(status.nozzle.actual, 221.4);
  assert.equal(status.bed.target, 60);
  assert.equal(status.chamber.actual, 37.5);
  assert.equal(status.coolingFan, 50);
  assert.equal(status.chamberFan, 100);
  assert.equal(status.tools.length, 1);
  assert.equal(status.tools[0].nozzleDiameter, 0.4);
  assert.equal(status.tools[0].filament.material, 'PETG');
  assert.equal(status.tools[0].filament.materialVariant, 'Basic');
  assert.equal(status.tools[0].filament.color, '#2F80ED');
  assert.equal(status.materials.toolCount, 1);
  assert.equal(status.materials.slotCount, 2);
  assert.deepEqual(status.materialInventory.map((slot) => [slot.index, slot.material, slot.color]), [
    [0, 'PLA', '#FF0000'],
    [1, 'PETG', '#2F80ED']
  ]);
});

test('normalizes H2 dual-extruder packed temperatures and active tool', () => {
  const status = normalizeBambuStatus({ print:{
    gcode_state:'RUNNING', subtask_name:'dual-head', mc_percent:15,
    bed_temper:80, bed_target_temper:80,
    device:{
      extruder:{ state:0x10, info:[
        { temp:packedTemp(190, 0), info:2 },
        { temp:packedTemp(251, 250), info:2 }
      ] },
      nozzle:{ info:[{ diameter:0.4 }, { diameter:0.6 }] },
      ctc:{ info:{ temp:packedTemp(52, 60) } }
    }
  } }, bambuModelProfile('H2D'));

  assert.equal(status.tools.length, 2);
  assert.equal(status.activeTool, 1);
  assert.equal(status.tools[1].active, true);
  assert.equal(status.tools[1].actual, 251);
  assert.equal(status.tools[1].target, 250);
  assert.equal(status.tools[1].nozzleDiameter, 0.6);
  assert.equal(status.chamber.actual, 52);
  assert.equal(status.chamber.target, 60);
});

test('Bambu SSDP parser recognises supported current model codes', () => {
  const p1 = parseBambuSsdpPacket([
    'NOTIFY * HTTP/1.1',
    'NT: urn:bambulab-com:device:3dprinter:1',
    'Location: 192.168.1.51',
    'USN: 01P123456789',
    'DevModel.bambu.com: C12',
    'DevName.bambu.com: Workshop P1S',
    '', ''
  ].join('\r\n'));
  const h2c = parseBambuSsdpPacket([
    'NOTIFY * HTTP/1.1',
    'NT: urn:bambulab-com:device:3dprinter:1',
    'Location: 192.168.1.52',
    'USN: 31B8123456789',
    'DevModel.bambu.com: O1C',
    'DevName.bambu.com: H2C',
    '', ''
  ].join('\r\n'));
  assert.ok(p1, 'P1S discovery packet should parse');
  assert.ok(h2c, 'H2C discovery packet should parse');
  assert.equal(p1.model, 'P1S');
  assert.equal(p1.adapterType, 'bambu-lab');
  assert.equal(h2c.model, 'H2C');
});

test('Bambu adapter validates all requested models and applies model-specific limits', () => {
  const expected = {
    P1S:[300,100,1], P2S:[300,110,1], H2S:[350,120,1], H2D:[350,120,2], H2C:[350,120,2]
  };
  for (const [model, [nozzleMax, bedMax, toolCount]] of Object.entries(expected)) {
    const config = prepareBambuConfig({ name:`Farm ${model}`, host:'192.168.1.50', model, serialNumber:`SERIAL-${model}`, accessCode:'12345678' });
    const adapter = getPrinterAdapter({ id:model, ...config });
    assert.equal(adapter.model, model);
    assert.equal(adapter.manufacturer, 'Bambu Lab');
    assert.equal(adapter.limits.nozzleTemperature.max, nozzleMax);
    assert.equal(adapter.limits.bedTemperature.max, bedMax);
    assert.equal(adapter.limits.toolCount, toolCount);
    assert.deepEqual(adapter.uploadExtensions, ['.gcode','.3mf']);
    assert.equal(adapter.capabilities.nativeMultiMaterialWorkflow, true);
    assert.equal(adapter.capabilities.toolTemperatures, toolCount > 1);
  }
  assert.throws(() => prepareBambuConfig({ name:'Bad', host:'192.168.1.50', model:'X1C', serialNumber:'x', accessCode:'x' }), /P1S, P2S, H2S, H2D, or H2C/);
});

test('Bambu access code remains backend-only and adapter is discoverable in registry metadata', () => {
  const config = prepareBambuConfig({ name:'P2', host:'192.168.1.55', model:'P2S', serialNumber:'22E123', accessCode:'super-secret' });
  const visible = publicPrinter({ id:'p2', ...config, createdAt:new Date(0).toISOString() });
  assert.equal(JSON.stringify(visible).includes('super-secret'), false);
  const definition = listAdapterDefinitions().find((entry) => entry.type === 'bambu-lab');
  assert.ok(definition);
  assert.deepEqual(definition.models, ['P1S','P2S','H2S','H2D','H2C']);
  assert.equal(definition.discovery, true);
});

test('Bambu camera factory returns model-appropriate snapshot source objects with live methods', () => {
  const p1 = createBambuCameraSource({ model:'P1S', host:'192.168.1.10', serialNumber:'01P1', adapterConfig:{ accessCode:'12345678' } });
  const h2 = createBambuCameraSource({ model:'H2D', host:'192.168.1.11', serialNumber:'0941', adapterConfig:{ accessCode:'12345678' } });
  assert.ok(p1 instanceof P1SnapshotSource);
  assert.ok(h2 instanceof RtspsSnapshotSource);
  assert.equal(p1.kind, 'snapshot');
  assert.equal(h2.kind, 'snapshot');
  assert.equal(typeof p1.getSnapshot, 'function');
  assert.equal(typeof h2.getSnapshot, 'function');
});

test('Bambu automatic queue allows known single-material G-code but holds native multi-material and 3MF jobs for review', () => {
  const adapter = {
    type:'bambu-lab',
    capabilities:{
      fileUpload:true,
      localFiles:true,
      printLocalFile:true,
      printToolMapping:false,
      nativeMultiMaterialWorkflow:true,
      projectFileMappingReview:true
    },
    limits:{ toolCount:1 },
    uploadExtensions:['.gcode','.3mf']
  };
  const state = {
    id:'bambu', name:'Bambu P1S', online:true,
    status:{ status:'idle', fileName:null,
      tools:[{ index:0, nozzleDiameter:0.4, filament:{ present:true, material:'PLA', color:'#FF0000' } }],
      materialInventory:[
        { index:0, present:true, material:'PLA', color:'#FF0000', source:'AMS 1 slot 1' },
        { index:1, present:true, material:'PETG', color:'#00FF00', source:'AMS 1 slot 2' }
      ]
    }
  };
  const single = evaluateQueueCompatibility({
    printer:{ id:'bambu' }, state, adapter,
    job:{ fileName:'single.gcode', requirements:{ toolCount:1, requiredTools:[0], logicalTools:[{ index:0, material:'PLA', color:'#FF0000', nozzleDiameter:0.4 }] } }
  });
  assert.equal(single.category, 'ready', JSON.stringify(single));

  const multi = evaluateQueueCompatibility({
    printer:{ id:'bambu' }, state, adapter,
    job:{ fileName:'multi.gcode', requirements:{ toolCount:2, requiredTools:[0,1], logicalTools:[{ index:0, material:'PLA', nozzleDiameter:0.4 },{ index:1, material:'PETG', nozzleDiameter:0.4 }] } }
  });
  assert.equal(multi.category, 'needs_review', JSON.stringify(multi));
  assert.ok(multi.reasons.some((reason) => reason.code === 'native_material_mapping_review'), JSON.stringify(multi));
  assert.deepEqual(multi.materialSlotMap, { '0':0, '1':1 });
  assert.equal(state.status.tools.length, 1, 'AMS slots must not inflate physical print-tool count');

  const impossibleNozzle = evaluateQueueCompatibility({
    printer:{ id:'bambu' }, state, adapter,
    job:{ fileName:'wrong-nozzle.gcode', requirements:{ toolCount:2, requiredTools:[0,1], logicalTools:[
      { index:0, material:'PLA', nozzleDiameter:0.4 },
      { index:1, material:'PETG', nozzleDiameter:0.6 }
    ] } }
  });
  assert.equal(impossibleNozzle.category, 'blocked', JSON.stringify(impossibleNozzle));
  assert.ok(impossibleNozzle.reasons.some((reason) => reason.code === 'nozzle_mismatch'), JSON.stringify(impossibleNozzle));

  const project = evaluateQueueCompatibility({
    printer:{ id:'bambu' }, state, adapter,
    job:{ fileName:'plate.gcode.3mf', requirements:{} }
  });
  assert.equal(project.category, 'needs_review', JSON.stringify(project));
  assert.ok(project.reasons.some((reason) => reason.code === 'bambu_project_mapping_review'), JSON.stringify(project));
});


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
