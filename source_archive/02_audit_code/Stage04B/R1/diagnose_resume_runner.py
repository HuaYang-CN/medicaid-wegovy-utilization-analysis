from common import *
import subprocess
step = 'diagnose_resume'
record('diagnose_resume_runner')
script = CODE / 'diagnose.py'
log = target(WORK / (step + '_command.log'))
assert not log.exists()
argv = [str(PY), '-u', '-B', str(script)]
jw(WORK / (step + '_command.json'), {'argv': argv, 'script_sha256': sha(script), 'network_requested': False})
with log.open('w', encoding='utf-8') as f:
    r = subprocess.run(argv, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, text=True, timeout=1800)
jw(WORK / (step + '_exit.json'), {'exit_code': r.returncode, 'log_sha256': sha(log)})
print(log.read_text(encoding='utf-8'))
sys.exit(r.returncode)
