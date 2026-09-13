from pathlib import Path

ROOT = Path('print-farm-controller')

def replace_once(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected exactly one match, found {text.count(old)} for {old!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

# Version bump.
replace_once('package.json', '"version": "0.12.6"', '"version": "0.12.7"')

# Show the existing RGB second line for FlashForge toolhead status as well as Snapmaker U1.
replace_once(
    'public/app.js',
    "${printer.adapterType === 'snapmaker-u1' ? `<small class=\"material-rgb",
    "${['snapmaker-u1','flashforge-ad5m'].includes(printer.adapterType) ? `<small class=\"material-rgb"
)

# Extend the UI regression and add a FlashForge-specific assertion.
test_path = ROOT / 'test/ui-print-setup.test.js'
test_text = test_path.read_text(encoding='utf-8')
test_text = test_text.replace(
    "assert.match(app, /printer\\.adapterType === 'snapmaker-u1'/);",
    "assert.match(app, /\\['snapmaker-u1','flashforge-ad5m'\\]\\.includes\\(printer\\.adapterType\\)/);",
    1
)
anchor = "\n\ntest('U1 print setup exposes native timelapse and filament safety controls', () => {"
new_test = """


test('FlashForge assigned filament colour shows hexadecimal and RGB values in toolhead status', () => {
  assert.match(app, /const values = \\[source, reported, filament\\.vendor \\|\\| filament\\.manufacturer, normalizeColor\\(filament\\.color\\)\\]/);
  assert.match(app, /\\['snapmaker-u1','flashforge-ad5m'\\]\\.includes\\(printer\\.adapterType\\)/);
  assert.match(app, /data-material-rgb=/);
  assert.match(app, /return `RGB\\(\\$\\{red\\}, \\$\\{green\\}, \\$\\{blue\\}\\)`/);
});
"""
if test_text.count(anchor) != 1:
    raise SystemExit('ui test insertion anchor not found exactly once')
test_path.write_text(test_text.replace(anchor, new_test + anchor, 1), encoding='utf-8')

# README release note.
readme = ROOT / 'README.md'
text = readme.read_text(encoding='utf-8')
text = text.replace('# Printer Fleet Controller v0.12.6', '# Printer Fleet Controller v0.12.7', 1)
marker = '# Printer Fleet Controller v0.12.7\n\n'
note = '> v0.12.7 shows FlashForge controller-assigned filament colours as both hexadecimal and **RGB(r, g, b)** values in Toolhead status. The stored colour and automatic queue compatibility behaviour are unchanged.\n\n'
if marker not in text:
    raise SystemExit('README title marker missing')
text = text.replace(marker, marker + note, 1)
readme.write_text(text, encoding='utf-8')

# Project handoff.
context = ROOT / 'PROJECT_CONTEXT.md'
text = context.read_text(encoding='utf-8')
text = text.replace('Current application version: **0.12.6**', 'Current application version: **0.12.7**', 1)
completed = '- **v0.12.6 Snapmaker RGB toolhead layout:** U1 toolhead status keeps the hexadecimal colour on the metadata line and renders `RGB(r, g, b)` on a separate line to prevent overflow; print setup and material preflight retain combined hex + RGB text.\n'
addition = '- **v0.12.7 FlashForge RGB colour display:** controller-assigned FlashForge filament colours now show the stored `#RRGGBB` value plus `RGB(r, g, b)` in Toolhead status; queue compatibility semantics are unchanged.\n'
if completed not in text:
    raise SystemExit('PROJECT_CONTEXT completed-work anchor missing')
text = text.replace(completed, completed + addition, 1)
old_task = '**v0.12.6 Snapmaker RGB toolhead layout is complete in code and automated tests.** Next priority is real-hardware validation that the split RGB line fits cleanly in all four U1 toolhead cards and that FlashForge colour assignments influence compatibility as expected.'
new_task = '**v0.12.7 FlashForge RGB colour display is complete in code and automated tests.** Next priority is real-hardware validation that assigned FlashForge colours show correctly in both hex and RGB and continue to influence compatibility as expected.'
if old_task not in text:
    raise SystemExit('PROJECT_CONTEXT current-task anchor missing')
text = text.replace(old_task, new_task, 1)
context.write_text(text, encoding='utf-8')
