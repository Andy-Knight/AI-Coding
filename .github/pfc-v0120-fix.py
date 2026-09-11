from pathlib import Path

path = Path('print-farm-controller/test/ui-print-setup.test.js')
text = path.read_text()
old = r"assert.match(server, /queue\\/production/);"
new = r"assert.match(server, /productionQueueMatch/);"
if old not in text:
    raise SystemExit('Generated production route assertion was not found')
path.write_text(text.replace(old, new, 1))
