from pathlib import Path
p = Path('.github/pfc-v0130-bambu-finalize.py')
text = p.read_text(encoding='utf-8')
old = "including manual assignments for third-party filament; RFID data is used as fallback. Nozzle size and XYZ offset come directly from each physical U1 extruder."
new = "including manual assignments for third-party filament; manually assigned filament colours can be written back to the idle printer. Official Snapmaker RFID colours remain locked. Nozzle size and XYZ offset come directly from each physical U1 extruder."
if old not in text:
    raise SystemExit('old U1 material-help anchor not found in finalize helper')
p.write_text(text.replace(old, new), encoding='utf-8')
print('Corrected current v0.12.8 material-help anchor')
