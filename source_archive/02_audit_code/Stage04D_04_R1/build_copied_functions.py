"""Build reviewed pure-function copies; never execute/import historical modules."""
import ast, hashlib, json
from pathlib import Path
ROOT = Path(__file__).absolute().parents[2]
D = ROOT / '02_audit_code/Stage04D_04_R1'
O = ROOT / '03_audit_outputs/Stage04D_04_R1/_working'

def extract(path, names):
    text = path.read_text(encoding='utf-8')
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    found = []
    for name in names:
        node = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name))
        found.append(''.join(lines[node.lineno - 1:node.end_lineno]))
    return '\n\n'.join(found) + '\n'
p = ROOT / '02_audit_code/Stage04C_R2_R2/independent_qa_v1.py'
q = ROOT / '02_audit_code/Stage04C_R2_R2/covariance_repair_v2.py'
copies = {'numerical_qa_v1.py': '"""Reviewed copied pure numerical/source functions; independent of primary GLM."""\nimport math\nimport numpy as np\nfrom scipy import stats\nimport audit_v1 as a\n\n' + extract(p, ['close', 'source_qa', 'newton', 'sandwich', 'infer']), 'covariance_v1.py': '"""Accepted stable covariance factor algorithm; no input/fit/writes on import."""\nimport numpy as np\nfrom scipy import linalg as la\n\n' + extract(q, ['native_factor'])}
for name, text in copies.items():
    dst = D / name
    assert not dst.exists()
    ast.parse(text)
    dst.write_text(text, encoding='utf-8')
O.mkdir(parents=True, exist_ok=True)
(O / 'copied_function_lineage.json').write_text(json.dumps({'static_only_no_historical_imports': True, 'origins': {str(s.relative_to(ROOT)): hashlib.sha256(s.read_bytes()).hexdigest() for s in [p, q]}, 'copies': {n: hashlib.sha256((D / n).read_bytes()).hexdigest() for n in copies}}, indent=2) + '\n', encoding='utf-8')
print('Reviewed pure functions copied; no models run')
