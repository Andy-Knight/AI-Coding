from pathlib import Path

script_path = Path('.pfc-update/apply-nozzle-designation.py')
source = script_path.read_text()
start_marker = "replace_once('src/store.js',\n\"\"\"function normalizeMaterialDesignation(value) {"
end_marker = "\nreplace_once('src/store.js',\n\"\"\"export async function reorderPrinters(printerIds) {\"\"\""
start = source.index(start_marker)
end = source.index(end_marker, start)
replacement = r'''replace_once('src/store.js',
"""  return text;
}

async function ensureStore() {""",
"""  return text;
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
'''
source = source[:start] + replacement + source[end:]
exec(compile(source, str(script_path), 'exec'))
