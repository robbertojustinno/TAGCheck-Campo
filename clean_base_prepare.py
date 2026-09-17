from pathlib import Path
import os, re, ast, hashlib, json, shutil
from urllib.parse import urlsplit

SOURCE=Path(r'H:\TAGUEAMENTO')
DEST=Path(r'H:\TAGCHECK_FASE2_CLEAN')
AUDIT=Path(r'H:\TAGCHECK\clean_base_evidence.json')
BACKUP=Path(r'H:\BACKUP_TAGCHECK_PRE_FASE2_2026-09-10')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(root):
    return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}

# Known compromised values are kept in memory only; never emitted or persisted.
known=set()
old=(BACKUP/'TAGUEAMENTO_COMPLETO/backend/main.py').read_text(encoding='utf-8-sig')
for node in ast.walk(ast.parse(old)):
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('ADMIN_PASSWORD','ADMIN_TOKEN') for t in node.targets):
        if isinstance(node.value,ast.Call) and len(node.value.args)>1:
            v=ast.literal_eval(node.value.args[1])
            if v: known.add(v)
private=(SOURCE/'backend/id.txt').read_text(encoding='utf-8-sig')
for u in re.findall(r'[a-zA-Z][a-zA-Z0-9+.-]*://[^\s]+',private):
    parsed=urlsplit(u)
    if parsed.password: known.add(parsed.password)
    if parsed.username and len(parsed.username)>6: known.add(parsed.username)
    known.add(u)

def excluded(rel):
    name=rel.name.lower()
    if any(p.lower() in ('.git','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','node_modules','venv','.venv','.cache') for p in rel.parts): return True
    if name=='.env.example':return False
    return (str(rel).replace('\\','/').lower()=='backend/id.txt' or name=='.env' or name.startswith('.env.')
        or name.startswith(('credentials','secrets','tokens'))
        or rel.suffix.lower() in ('.zip','.bak','.tmp','.temp','.log','.pyc','.pyo','.pyd','.key','.pem','.pfx','.p12')
        or name.endswith('~'))

patterns=[
 ('authenticated URL',r'[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/"\'<>:]+:[^\s/@"\'<>]+@'),
 ('private key',r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----'),
 ('provider credential',r'\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-proj-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,})'),
 ('JWT literal',r'\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}'),
 ('database URL',r'(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s"\'<>]+'),
]

def scan(root):
    errors=[]; candidates=[]; count=0
    for p in root.rglob('*'):
        if not p.is_file() or '.git' in p.relative_to(root).parts:continue
        rel=str(p.relative_to(root)); data=p.read_bytes(); count+=1
        text=data.decode('utf-8-sig',errors='replace')
        for n,line in enumerate(text.splitlines(),1):
            for v in known:
                if v in line:errors.append((rel,n,'known compromised value'))
            for kind,pattern in patterns:
                if re.search(pattern,line):errors.append((rel,n,kind))
            # Enumerate nonempty secret-like literal assignments for manual review.
            m=re.search(r'''(?i)\b([a-z_]*(?:password|passwd|senha|token|secret|api_key)[a-z_]*)\s*[=:]\s*(['"])(.*?)\2''',line)
            if m and m[3]:
                # Dictionary labels, DOM identifiers and storage-key names are not credentials.
                candidates.append((rel,n,m[1],'literal length '+str(len(m[3]))))
    print('Scanned files:',count)
    for f,n,kind in sorted(set(errors)):print('STOP:',f,'line',n,kind)
    for f,n,name,kind in candidates:print('REVIEW:',f,'line',n,'identifier',name,kind)
    if errors:raise SystemExit('Secret scan blocked further work')
    env=(root/'.env.example').read_text(encoding='utf-8-sig')
    assert all(not line.strip() or line.lstrip().startswith('#') or ('=' in line and not line.split('=',1)[1].strip()) for line in env.splitlines())
    assert not (root/'backend/id.txt').exists()
    assert not any(p.name=='.env' or (p.name.startswith('.env.') and p.name!='.env.example') for p in root.rglob('*'))
    print('No detected secrets; .env.example contains only empty placeholders.')
    return candidates

if __name__=='__main__':
    assert not DEST.exists(),'Destination exists; no overwrite permitted'
    original=snapshot(SOURCE)
    backup_meta={str(p.relative_to(BACKUP)):sha(p) for p in BACKUP.iterdir() if p.is_file()}
    paths=[]; skipped=[]
    for base,dirs,files in os.walk(SOURCE):
        dirs[:]=[d for d in dirs if not excluded((Path(base)/d).relative_to(SOURCE))]
        for name in files:
            p=Path(base)/name; rel=p.relative_to(SOURCE)
            if p.is_symlink():raise SystemExit('Symbolic link encountered; copy stopped')
            if excluded(rel):skipped.append(str(rel));continue
            # Prevent known secret transfer, including authenticated URLs and private keys.
            text=p.read_bytes().decode('utf-8-sig',errors='replace')
            for n,line in enumerate(text.splitlines(),1):
                if any(v in line for v in known) or any(re.search(pattern,line) for _,pattern in patterns):
                    print('STOP before copy:',str(rel),'line',n)
                    raise SystemExit(1)
            paths.append((p,rel))
    DEST.mkdir()
    for p,rel in paths:
        target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        assert sha(p)==sha(target)
    ignore=DEST/'.gitignore'
    content=ignore.read_text(encoding='utf-8-sig')
    if 'tokens*' not in content.splitlines():content=content.rstrip()+'\ntokens*\n'
    ignore.write_bytes(content.encode('utf-8'))
    # Preserve repeatable tests with paths relative to this new repository.
    tests=DEST/'tests';tests.mkdir()
    py=Path(r'H:\TAGCHECK\phase15_test.py').read_text(encoding='utf-8')
    py=py.replace("ROOT=Path(r'H:\\TAGUEAMENTO')",'ROOT=Path(__file__).resolve().parents[1]')
    (tests/'test_stabilization.py').write_bytes(py.encode('utf-8'))
    js=Path(r'H:\TAGCHECK\phase15_qr_test.js').read_text(encoding='utf-8')
    js=js.replace("'H:/TAGUEAMENTO/viewer/app.js'","require('path').join(__dirname, '../viewer/app.js')")
    (tests/'qr.test.js').write_bytes(js.encode('utf-8'))
    candidates=scan(DEST)
    AUDIT.write_text(json.dumps({'source':original,'backup_metadata':backup_meta,'copied':len(paths),'excluded':skipped,'candidates':candidates},indent=2),encoding='utf-8')
    print('Copied:',len(paths),'Excluded:',skipped)
    print('Final functional files including tests:',sum(p.is_file() for p in DEST.rglob('*')))
