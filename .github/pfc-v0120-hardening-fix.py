from pathlib import Path

path = Path('print-farm-controller/src/print-queue.js')
text = path.read_text()
old = """    } catch (error) {\n      if (job.status === 'starting') {\n        this.markTerminal(job, 'failed', error.message || 'Automatic queued print failed to start', { requireBedClearance:true });\n      } else {\n        job.status = 'needs_review';\n        job.error = `${job.printerName || 'Selected printer'}: ${error.message || 'Automatic queue preparation failed'}`;\n        job.updatedAt = nowIso();\n      }\n      await this.persistAndNotify();\n"""
new = """    } catch (error) {\n      if (TERMINAL_STATES.has(job.status)) {\n        await this.persistAndNotify();\n        return;\n      }\n      if (job.productionPaused === true) {\n        this.resetAutomaticAssignment(job);\n        await this.persistAndNotify();\n        return;\n      }\n      if (job.status === 'starting') {\n        this.markTerminal(job, 'failed', error.message || 'Automatic queued print failed to start', { requireBedClearance:true });\n      } else {\n        job.status = 'needs_review';\n        job.error = `${job.printerName || 'Selected printer'}: ${error.message || 'Automatic queue preparation failed'}`;\n        job.updatedAt = nowIso();\n      }\n      await this.persistAndNotify();\n"""
if old not in text:
    raise SystemExit('automatic start catch anchor not found')
path.write_text(text.replace(old, new, 1))
