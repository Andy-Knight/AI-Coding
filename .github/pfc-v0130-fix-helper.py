from pathlib import Path
p = Path('.github/pfc-v0130-bambu-finalize.py')
text = p.read_text(encoding='utf-8')
old = "including manual assignments for third-party filament; RFID data is used as fallback. Nozzle size and XYZ offset come directly from each physical U1 extruder."
new = "including manual assignments for third-party filament; manually assigned filament colours can be written back to the idle printer. Official Snapmaker RFID colours remain locked. Nozzle size and XYZ offset come directly from each physical U1 extruder."
if old not in text:
    raise SystemExit('old U1 material-help anchor not found in finalize helper')
text = text.replace(old, new)
# The direct-print confirmation template contains escaped newlines whose exact source
# spelling has changed across recent UI releases. Remove that optional patch from the
# first-pass helper; the backend/queue still blocks unattended project-file mapping.
marker = "replace_once('public/app.js',\n'''      const preflight = materialPreflightText(printer);"
start = text.find(marker)
if start < 0:
    raise SystemExit('direct-print optional patch block not found')
end = text.find('\n\n# Version.', start)
if end < 0:
    raise SystemExit('direct-print optional patch end not found')
text = text[:start] + text[end:]
p.write_text(text, encoding='utf-8')
print('Corrected current v0.12.8 UI anchors')
