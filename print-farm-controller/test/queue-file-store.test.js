import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

async function loadStoreInTempDir() {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'pfc-queue-files-test-'));
  process.env.DATA_DIR = dir;
  const moduleUrl = pathToFileURL(path.resolve('src/queue-file-store.js'));
  moduleUrl.searchParams.set('case', `${Date.now()}-${Math.random()}`);
  const mod = await import(moduleUrl.href);
  return { dir, ...mod };
}

test('persistent queue file staging stores hash, requirements and exact bytes', async () => {
  const { dir, stageQueueFile, getQueueFile, removeQueueFile } = await loadStoreInTempDir();
  const source = path.join(dir, 'source.gcode');
  const content = '; filament_type = PLA\n; filament_colour = #FF0000\n; nozzle_diameter = 0.4\nT0\nG1 X10\n';
  await fs.writeFile(source, content);
  const staged = await stageQueueFile(source, 'gearbox-cover.gcode');
  assert.equal(staged.fileName, 'gearbox-cover.gcode');
  assert.equal(staged.size, Buffer.byteLength(content));
  assert.match(staged.sha256, /^[0-9a-f]{64}$/);
  assert.deepEqual(staged.requirements.requiredTools, [0]);
  assert.equal(staged.requirements.logicalTools[0].material, 'PLA');
  assert.equal(staged.requirements.logicalTools[0].color, '#FF0000');
  assert.equal(staged.requirements.logicalTools[0].nozzleDiameter, 0.4);

  const resolved = await getQueueFile(staged.id);
  assert.equal(await fs.readFile(resolved.filePath, 'utf8'), content);
  await removeQueueFile(staged.id);
  await assert.rejects(() => getQueueFile(staged.id));
  await fs.rm(dir, { recursive:true, force:true });
});
