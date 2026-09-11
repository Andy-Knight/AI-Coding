import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

test('dashboard order persists and new printers append after a custom order', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'ff-fleet-order-'));
  process.env.DATA_DIR = dir;
  const store = await import(`../src/store.js?order-test=${Date.now()}`);

  try {
    const a = await store.addPrinter({ name:'Zulu', host:'10.0.0.1', serialNumber:'A', checkCode:'1' });
    const b = await store.addPrinter({ name:'Alpha', host:'10.0.0.2', serialNumber:'B', checkCode:'2' });
    assert.equal(store.publicPrinter(a).dashboardOrder, null);
    assert.equal(store.publicPrinter(b).dashboardOrder, null);

    await store.reorderPrinters([b.id, a.id]);
    const ordered = await store.listPrinters();
    assert.equal(ordered.find((p) => p.id === b.id).dashboardOrder, 0);
    assert.equal(ordered.find((p) => p.id === a.id).dashboardOrder, 1);

    const c = await store.addPrinter({ name:'New', host:'10.0.0.3', serialNumber:'C', checkCode:'3' });
    assert.equal(c.dashboardOrder, 2);
  } finally {
    delete process.env.DATA_DIR;
    await rm(dir, { recursive:true, force:true });
  }
});

test('dashboard order rejects incomplete lists', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'ff-fleet-order-invalid-'));
  process.env.DATA_DIR = dir;
  const store = await import(`../src/store.js?order-invalid-test=${Date.now()}`);

  try {
    const a = await store.addPrinter({ name:'One', host:'10.0.1.1', serialNumber:'A', checkCode:'1' });
    await store.addPrinter({ name:'Two', host:'10.0.1.2', serialNumber:'B', checkCode:'2' });
    await assert.rejects(() => store.reorderPrinters([a.id]), /every configured printer exactly once/);
  } finally {
    delete process.env.DATA_DIR;
    await rm(dir, { recursive:true, force:true });
  }
});

test('legacy stored FlashForge printers are hydrated with adapter metadata without re-adding them', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'ff-fleet-adapter-migration-'));
  process.env.DATA_DIR = dir;
  const legacy = [{
    id:'legacy-1', name:'Legacy Pro', host:'10.0.2.1', serialNumber:'SN', checkCode:'CODE',
    httpPort:8898, tcpPort:8899, cameraPort:8080, createdAt:'2026-01-01T00:00:00.000Z'
  }];
  const { writeFile } = await import('node:fs/promises');
  await writeFile(path.join(dir, 'printers.json'), JSON.stringify(legacy));
  const store = await import(`../src/store.js?adapter-migration-test=${Date.now()}`);

  try {
    const [printer] = await store.listPrinters();
    assert.equal(printer.adapterType, 'flashforge-ad5m');
    assert.equal(printer.manufacturer, 'FlashForge');
    assert.equal(printer.model, 'Adventurer 5M Pro');
    assert.equal(store.publicPrinter(printer).adapterType, 'flashforge-ad5m');
  } finally {
    delete process.env.DATA_DIR;
    await rm(dir, { recursive:true, force:true });
  }
});

test('FlashForge manual material designation persists without exposing adapter secrets', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'ff-fleet-material-designation-'));
  process.env.DATA_DIR = dir;
  const store = await import(`../src/store.js?material-designation-test=${Date.now()}`);

  try {
    const printer = await store.addPrinter({
      name:'Material Test', host:'10.0.3.1', serialNumber:'SN', checkCode:'CODE',
      adapterConfig:{ secretValue:'keep-private' }
    });
    const assigned = await store.setPrinterMaterialDesignation(printer.id, 'PETG-CF');
    assert.equal(assigned.adapterConfig.filamentDesignation, 'PETG-CF');
    assert.equal(assigned.adapterConfig.secretValue, 'keep-private');
    assert.equal(store.publicPrinter(assigned).materialDesignation, 'PETG-CF');
    assert.equal('adapterConfig' in store.publicPrinter(assigned), false);

    const cleared = await store.setPrinterMaterialDesignation(printer.id, null);
    assert.equal(cleared.adapterConfig.filamentDesignation, undefined);
    assert.equal(cleared.adapterConfig.secretValue, 'keep-private');
    assert.equal(store.publicPrinter(cleared).materialDesignation, null);
  } finally {
    delete process.env.DATA_DIR;
    await rm(dir, { recursive:true, force:true });
  }
});

test('printer controller name can be renamed without changing connection identity', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'ff-fleet-rename-'));
  process.env.DATA_DIR = dir;
  const store = await import(`../src/store.js?rename-test=${Date.now()}`);

  try {
    const printer = await store.addPrinter({
      name:'Original Name', host:'10.0.4.1', serialNumber:'SERIAL-1', checkCode:'CODE-1',
      adapterConfig:{ apiKey:'private' }
    });
    const renamed = await store.renamePrinter(printer.id, 'Workshop U1');
    assert.equal(renamed.name, 'Workshop U1');
    assert.equal(renamed.host, '10.0.4.1');
    assert.equal(renamed.serialNumber, 'SERIAL-1');
    assert.equal(renamed.checkCode, 'CODE-1');
    assert.equal(renamed.adapterConfig.apiKey, 'private');
    assert.equal(store.publicPrinter(renamed).name, 'Workshop U1');
    await assert.rejects(() => store.renamePrinter(printer.id, '   '), /Printer name is required/);
  } finally {
    delete process.env.DATA_DIR;
    await rm(dir, { recursive:true, force:true });
  }
});
