"""Explicit one-step runner; project-only logs, no installations/network."""
from common import *
import subprocess
step = sys.argv[1]
assert step in {'inputs', 'diagnose', 'fit', 'release'}
script = CODE / (step + '.py')
log = target(WORK / (step + '_command.log'))
assert not log.exists(), 'preserve existing attempt; use a versioned runner for repairs'
argv = [str(PY if step != 'release' else Path(sys.executable)), '-u', '-B', str(script)]
env = os.environ.copy()
env.update(PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
jw(WORK / (step + '_command.json'), {'argv': argv, 'script_sha256': sha(script), 'network_requested': False, 'cwd': str(ROOT)})
with log.open('w', encoding='utf-8') as f:
    r = subprocess.run(argv, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, text=True, timeout=1800)
jw(WORK / (step + '_exit.json'), {'exit_code': r.returncode, 'log_sha256': sha(log)})
print(log.read_text(encoding='utf-8'))
sys.exit(r.returncode)
