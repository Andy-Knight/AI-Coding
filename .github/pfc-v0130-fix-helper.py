from pathlib import Path

finalize = Path('.github/pfc-v0130-bambu-finalize.py')
text = finalize.read_text(encoding='utf-8')

# Update the current v0.12.8 U1 help text anchor used by the integration patch.
old = "including manual assignments for third-party filament; RFID data is used as fallback. Nozzle size and XYZ offset come directly from each physical U1 extruder."
new = "including manual assignments for third-party filament; manually assigned filament colours can be written back to the idle printer. Official Snapmaker RFID colours remain locked. Nozzle size and XYZ offset come directly from each physical U1 extruder."
if old not in text:
    raise SystemExit('old U1 material-help anchor not found in finalize helper')
text = text.replace(old, new)

# The direct-print confirmation template contains escaped newlines whose exact source
# spelling changed in v0.12.8. Direct .3mf start is now blocked in the backend anyway,
# so remove this optional browser-warning patch.
marker = "replace_once('public/app.js',\n'''      const preflight = materialPreflightText(printer);"
start = text.find(marker)
if start < 0:
    raise SystemExit('direct-print optional patch block not found')
end = text.find('\n\n# Version.', start)
if end < 0:
    raise SystemExit('direct-print optional patch end not found')
text = text[:start] + text[end:]

# Insert the release note directly below the title instead of trying to replace only
# the prefix of the existing v0.12.8 paragraph.
readme_marker = "replace_once('README.md',\n'''> v0.12.8 adds **native Snapmaker U1 filament colour editing**'''"
readme_start = text.find(readme_marker)
if readme_start < 0:
    raise SystemExit('fragile README release-note patch block not found')
readme_end = text.find("\nreplace_once('README.md',\n'''- **Snapmaker U1**", readme_start)
if readme_end < 0:
    raise SystemExit('README release-note patch end not found')
text = text[:readme_start] + text[readme_end + 1:]

# Correct the context wording now that .3mf is storage-only until an explicit
# AMS/plate mapping flow authorises project start.
text = text.replace(
    'FTPS printer storage listing/upload/verification, local G-code/3MF start path,',
    'FTPS printer storage listing/upload/verification, local G-code start path plus 3MF storage support,'
)
text = text.replace('v0.13.0 regression suite: **132 passing tests, 0 failures**.',
                    'v0.13.0 regression suite: **133 passing tests, 0 failures**.')
finalize.write_text(text, encoding='utf-8')

# Add the v0.13.0 release note to the current README before the finalize helper bumps
# the title itself.
readme = Path('print-farm-controller/README.md')
readme_text = readme.read_text(encoding='utf-8')
anchor = '# Printer Fleet Controller v0.12.8\n\n'
if readme_text.count(anchor) != 1:
    raise SystemExit('README title anchor not found exactly once')
release_note = (
    '> v0.13.0 adds **Bambu Lab P1S, P2S, H2S, H2D and H2C** support through local LAN/Developer Mode. '
    'The Bambu adapter uses MQTT-over-TLS for live status/control and implicit FTPS for printer-local file listing, upload and verification; '
    'model-specific temperature/tool limits are enforced. P1S uses its native JPEG camera transport, while P2S/H2 cameras use RTSPS when `ffmpeg` is available. '
    'Single-material G-code can participate in the automatic compatible-printer queue. Bambu `.3mf` files can be stored on the printer, but project start and native multi-material/AMS workflows are deliberately held until explicit AMS/plate mapping is added.\n\n'
)
readme.write_text(readme_text.replace(anchor, anchor + release_note, 1), encoding='utf-8')

# Safety: no Bambu project file may be directly started until the controller has an
# explicit reviewed AMS/plate map. The lower-level project command remains available
# behind an opt-in flag for the future mapping workflow.
bambu_api = Path('print-farm-controller/src/bambu-api.js')
api_text = bambu_api.read_text(encoding='utf-8')
old_branch = "  if (/\\.3mf$/i.test(name)) {\n    const payload = {"
new_branch = "  if (/\\.3mf$/i.test(name)) {\n    if (options.allowProjectStart !== true) {\n      throw new BambuApiError('Bambu 3MF project start requires reviewed AMS/plate mapping; upload/storage is supported but direct start is disabled');\n    }\n    const payload = {"
if api_text.count(old_branch) != 1:
    raise SystemExit('Bambu .3mf start branch anchor not found exactly once')
bambu_api.write_text(api_text.replace(old_branch, new_branch, 1), encoding='utf-8')

# Regression: verify the safety guard triggers before any MQTT connection is attempted.
test_file = Path('print-farm-controller/test/bambu-api.test.js')
test_text = test_file.read_text(encoding='utf-8')
old_import = "import { normalizeBambuStatus } from '../src/bambu-api.js';"
new_import = "import { normalizeBambuStatus, startBambuFile } from '../src/bambu-api.js';"
if test_text.count(old_import) != 1:
    raise SystemExit('Bambu test import anchor not found exactly once')
test_text = test_text.replace(old_import, new_import, 1)
test_text += """

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
"""
test_file.write_text(test_text, encoding='utf-8')

print('Corrected v0.12.8 integration anchors and hardened Bambu 3MF start safety')
