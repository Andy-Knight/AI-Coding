from pathlib import Path

root = Path('print-farm-controller')


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'missing patch target: {label}')
    if text.count(old) != 1:
        raise SystemExit(f'patch target not unique ({text.count(old)}): {label}')
    return text.replace(old, new, 1)

app_path = root / 'public' / 'app.js'
app = app_path.read_text()
app = replace_once(app,
"""function materialSwatchColor(filament = {}) {
  return /^#[0-9A-Fa-f]{6}$/.test(String(filament.color || '')) ? filament.color : null;
}
""",
"""function materialSwatchColor(filament = {}) {
  return /^#[0-9A-Fa-f]{6}$/.test(String(filament.color || '')) ? filament.color : null;
}

function filamentColorText(value) {
  const color = normalizeColor(value);
  if (!color) return null;
  const red = Number.parseInt(color.slice(1, 3), 16);
  const green = Number.parseInt(color.slice(3, 5), 16);
  const blue = Number.parseInt(color.slice(5, 7), 16);
  return `${color} · RGB(${red}, ${green}, ${blue})`;
}
""", 'colour formatter')
app = replace_once(app,
"""  const values = [source, reported, filament.vendor || filament.manufacturer, filament.color].filter(Boolean);
""",
"""  const values = [source, reported, filament.vendor || filament.manufacturer, filamentColorText(filament.color)].filter(Boolean);
""", 'toolhead metadata colour')
app = replace_once(app,
"""    const color = filament.color ? ` · ${filament.color}` : '';
""",
"""    const colorText = filamentColorText(filament.color);
    const color = colorText ? ` · ${colorText}` : '';
""", 'material preflight colour')
app = replace_once(app,
"""  const color = materialSwatchColor(filament);
  const presence = filamentPresenceText(filament);
  const nozzle = nozzleDiameterText(tool?.nozzleDiameter);
  const swatch = `<span class=\"material-swatch${color ? '' : ' unknown'}\"${color ? ` style=\"background:${escapeHtml(color)}\"` : ''} title=\"${escapeHtml(color ? 'Configured filament colour' : 'Colour unknown')}\"></span>`;
  const text = `<span class=\"tool-map-choice-text\"><strong>T${tool.index} · ${escapeHtml(material)}</strong><small>${escapeHtml(`${presence} · ${nozzle}`)}</small></span>`;
""",
"""  const color = materialSwatchColor(filament);
  const colorText = filamentColorText(filament.color);
  const presence = filamentPresenceText(filament);
  const nozzle = nozzleDiameterText(tool?.nozzleDiameter);
  const swatch = `<span class=\"material-swatch${color ? '' : ' unknown'}\"${color ? ` style=\"background:${escapeHtml(color)}\"` : ''} title=\"${escapeHtml(color ? 'Configured filament colour' : 'Colour unknown')}\"></span>`;
  const details = [presence, colorText, nozzle].filter(Boolean).join(' · ');
  const text = `<span class=\"tool-map-choice-text\"><strong>T${tool.index} · ${escapeHtml(material)}</strong><small>${escapeHtml(details)}</small></span>`;
""", 'U1 physical tool picker colour')
app_path.write_text(app)

test_path = root / 'test' / 'ui-print-setup.test.js'
tests = test_path.read_text()
anchor = """test('U1 print setup exposes native timelapse and filament safety controls', () => {
"""
new_test = """test('Snapmaker U1 filament colours display both hexadecimal and RGB values', () => {
  assert.match(app, /function filamentColorText/);
  assert.match(app, /RGB\\(\\$\\{red\\}, \\$\\{green\\}, \\$\\{blue\\}\\)/);
  assert.match(app, /filamentColorText\\(filament\\.color\\)/);
  assert.match(app, /const details = \\[presence, colorText, nozzle\\]/);
});


"""
if new_test.strip() not in tests:
    tests = replace_once(tests, anchor, new_test + anchor, 'UI RGB regression test anchor')
test_path.write_text(tests)

package_path = root / 'package.json'
package = package_path.read_text()
package = replace_once(package, '"version": "0.12.4"', '"version": "0.12.5"', 'package version')
package_path.write_text(package)

readme_path = root / 'README.md'
readme = readme_path.read_text()
readme = replace_once(readme, '# Printer Fleet Controller v0.12.4', '# Printer Fleet Controller v0.12.5', 'README version')
readme = replace_once(readme,
'> v0.12.4 adds a persistent **filament colour designation** alongside material type for FlashForge printers.',
'> v0.12.5 shows Snapmaker U1 filament colours as both hexadecimal and **RGB(r, g, b)** values in toolhead metadata, material preflight, and physical-head choices.\n\n> v0.12.4 adds a persistent **filament colour designation** alongside material type for FlashForge printers.',
'README release note')
readme_path.write_text(readme)

context_path = root / 'PROJECT_CONTEXT.md'
context = context_path.read_text()
context = replace_once(context, 'Current application version: **0.12.4**', 'Current application version: **0.12.5**', 'context version')
context = replace_once(context,
'- **v0.12.4 FlashForge filament colour designation:** FlashForge printer detail controls now persist both material type and `#RRGGBB` filament colour; the assigned colour is normalized into tool status and participates in automatic queue compatibility/mismatch blocking.\n',
'- **v0.12.4 FlashForge filament colour designation:** FlashForge printer detail controls now persist both material type and `#RRGGBB` filament colour; the assigned colour is normalized into tool status and participates in automatic queue compatibility/mismatch blocking.\n- **v0.12.5 Snapmaker RGB colour display:** U1 filament colours are shown as both `#RRGGBB` and `RGB(r, g, b)` in toolhead metadata, print setup physical-head choices, and material preflight.\n- v0.12.5 regression suite: **121 passing tests, 0 failures**.\n',
'context completed work')
context = replace_once(context,
'**v0.12.4 FlashForge filament colour designation is complete in code and automated tests.** Next priority is real-hardware validation that material/colour assignments render correctly and influence automatic compatibility as expected.',
'**v0.12.5 Snapmaker RGB colour display is complete in code and automated tests.** Next priority is real-hardware validation that FlashForge assignments and Snapmaker RGB values render correctly and influence compatibility as expected.',
'context current task')
context_path.write_text(context)
