from pathlib import Path
import json

ROOT = Path('print-farm-controller')

def replace_once(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'Expected text not found in {path}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

# Version
package_path = ROOT / 'package.json'
package = json.loads(package_path.read_text(encoding='utf-8'))
if package.get('version') != '0.12.5':
    raise SystemExit(f"Expected package version 0.12.5, got {package.get('version')}")
package['version'] = '0.12.6'
package_path.write_text(json.dumps(package, indent=2) + '\n', encoding='utf-8')

# UI: keep hex on metadata line, move U1 RGB to its own line.
replace_once('public/app.js',
"""  const values = [source, reported, filament.vendor || filament.manufacturer, filamentColorText(filament.color)].filter(Boolean);\n  return values.length ? values.join(' · ') : 'No material metadata';\n}""",
"""  const values = [source, reported, filament.vendor || filament.manufacturer, normalizeColor(filament.color)].filter(Boolean);\n  return values.length ? values.join(' · ') : 'No material metadata';\n}""")

replace_once('public/app.js',
"""function filamentColorText(value) {\n  const color = normalizeColor(value);\n  if (!color) return null;\n  const red = Number.parseInt(color.slice(1, 3), 16);\n  const green = Number.parseInt(color.slice(3, 5), 16);\n  const blue = Number.parseInt(color.slice(5, 7), 16);\n  return `${color} · RGB(${red}, ${green}, ${blue})`;\n}""",
"""function filamentRgbText(value) {\n  const color = normalizeColor(value);\n  if (!color) return null;\n  const red = Number.parseInt(color.slice(1, 3), 16);\n  const green = Number.parseInt(color.slice(3, 5), 16);\n  const blue = Number.parseInt(color.slice(5, 7), 16);\n  return `RGB(${red}, ${green}, ${blue})`;\n}\n\nfunction filamentColorText(value) {\n  const color = normalizeColor(value);\n  if (!color) return null;\n  return `${color} · ${filamentRgbText(color)}`;\n}""")

replace_once('public/app.js',
"""      set(`[data-material-meta=\"${tool.index}\"]`, filamentMetaText(filament));\n      row.classList.toggle('filament-missing', filament.present === false);""",
"""      set(`[data-material-meta=\"${tool.index}\"]`, filamentMetaText(filament));\n      const rgbText = filamentRgbText(filament.color);\n      set(`[data-material-rgb=\"${tool.index}\"]`, rgbText || '');\n      const rgbLine = row.querySelector(`[data-material-rgb=\"${tool.index}\"]`);\n      rgbLine?.classList.toggle('hidden', !rgbText);\n      row.classList.toggle('filament-missing', filament.present === false);""")

replace_once('public/app.js',
"""          <small data-material-meta=\"${tool.index}\">${escapeHtml(filamentMetaText(filament))}</small>\n        </div>`;""",
"""          <small data-material-meta=\"${tool.index}\">${escapeHtml(filamentMetaText(filament))}</small>\n          ${printer.adapterType === 'snapmaker-u1' ? `<small class=\"material-rgb${filamentRgbText(filament.color) ? '' : ' hidden'}\" data-material-rgb=\"${tool.index}\">${escapeHtml(filamentRgbText(filament.color) || '')}</small>` : ''}\n        </div>`;""")

replace_once('public/styles.css',
""".material-tool > small { color:#687986; font-size:.69rem; margin-top:4px; }""",
""".material-tool > small { color:#687986; font-size:.69rem; margin-top:4px; }\n.material-tool > small.material-rgb { color:#8193a2; margin-top:2px; }""")

# Regression coverage.
replace_once('test/ui-print-setup.test.js',
"""test('Snapmaker U1 filament colours display both hexadecimal and RGB values', () => {\n  assert.match(app, /function filamentColorText/);\n  assert.match(app, /RGB\\(\\$\\{red\\}, \\$\\{green\\}, \\$\\{blue\\}\\)/);\n  assert.match(app, /filamentColorText\\(filament\\.color\\)/);\n  assert.match(app, /const details = \\[presence, colorText, nozzle\\]/);\n});""",
"""test('Snapmaker U1 toolhead status puts RGB colour on a dedicated second line', () => {\n  assert.match(app, /function filamentRgbText/);\n  assert.match(app, /RGB\\(\\$\\{red\\}, \\$\\{green\\}, \\$\\{blue\\}\\)/);\n  assert.match(app, /data-material-rgb=/);\n  assert.match(app, /printer\\.adapterType === 'snapmaker-u1'/);\n  assert.match(app, /rgbLine\\?\\.classList\\.toggle\\('hidden', !rgbText\\)/);\n  assert.match(styles, /\\.material-tool > small\\.material-rgb/);\n  assert.doesNotMatch(app, /const values = \\[source, reported, filament\\.vendor \\|\\| filament\\.manufacturer, filamentColorText\\(filament\\.color\\)\\]/);\n  assert.match(app, /const details = \\[presence, colorText, nozzle\\]/);\n});""")

# README
replace_once('README.md', '# Printer Fleet Controller v0.12.5', '# Printer Fleet Controller v0.12.6')
replace_once('README.md',
"> v0.12.5 shows Snapmaker U1 filament colours as both hexadecimal and **RGB(r, g, b)** values in toolhead metadata, material preflight, and physical-head choices.\n",
"> v0.12.6 keeps the Snapmaker U1 hexadecimal filament colour on the main toolhead metadata line and moves **RGB(r, g, b)** onto its own line so the value fits cleanly inside each toolhead status card. Print setup and material preflight keep the combined hex + RGB display.\n\n> v0.12.5 shows Snapmaker U1 filament colours as both hexadecimal and **RGB(r, g, b)** values in toolhead metadata, material preflight, and physical-head choices.\n")

# Project context
replace_once('PROJECT_CONTEXT.md', '- Current application version: **0.12.5**', '- Current application version: **0.12.6**')
replace_once('PROJECT_CONTEXT.md',
"- v0.12.5 regression suite: **121 passing tests, 0 failures**.\n",
"- v0.12.5 regression suite: **121 passing tests, 0 failures**.\n- **v0.12.6 Snapmaker RGB toolhead layout:** U1 toolhead status keeps the hexadecimal colour on the metadata line and renders `RGB(r, g, b)` on a separate line to prevent overflow; print setup and material preflight retain combined hex + RGB text.\n")
replace_once('PROJECT_CONTEXT.md',
"**v0.12.5 Snapmaker RGB colour display is complete in code and automated tests.** Next priority is real-hardware validation that FlashForge assignments and Snapmaker RGB values render correctly and influence compatibility as expected.",
"**v0.12.6 Snapmaker RGB toolhead layout is complete in code and automated tests.** Next priority is real-hardware validation that the split RGB line fits cleanly in all four U1 toolhead cards and that FlashForge colour assignments influence compatibility as expected.")
