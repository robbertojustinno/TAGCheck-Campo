from pathlib import Path
import subprocess, ast, re, hashlib, json
r=Path(r'H:\TAGUEAMENTO')
b=Path(r'H:\BACKUP_TAGCHECK_PRE_FASE2_2026-09-10')
old=(b/'TAGUEAMENTO_COMPLETO/backend/main.py').read_text(encoding='utf-8-sig')
known=[]
for node in ast.walk(ast.parse(old)):
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('ADMIN_PASSWORD','ADMIN_TOKEN') for t in node.targets):
        if isinstance(node.value,ast.Call) and len(node.value.args)>1:
            value=ast.literal_eval(node.value.args[1])
            if value: known.append(value)
cfg=(b/'TAGUEAMENTO_COMPLETO/admin/config.js').read_text(encoding='utf-8-sig')
key=re.search(r"authToken:\s*['\"]([^'\"]+)",cfg).group(1)
print('Legacy storage key equals old server credential:', key in known)
for path in r.rglob('*'):
    if not path.is_file() or '.git' in path.parts or path.suffix.lower() not in ('.js','.py','.html','.yaml','.txt','.json','.md'): continue
    data=path.read_text(encoding='utf-8-sig',errors='replace')
    findings=[]
    if any(value in data for value in known): findings.append('legacy credential literal')
    if re.search(r'://[^\s/:]+:[^\s/@]+@',data): findings.append('authenticated URL')
    if findings: print(str(path.relative_to(r)), ', '.join(findings))
count=0
for row in (b/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines():
    sha,relative=row.split('  ',1)
    assert hashlib.sha256((b/relative).read_bytes()).hexdigest().upper()==sha.upper(),relative
    count+=1
print('Original backup manifest: all',count,'hashes unchanged')
changed=[]; missing=[]
for oldpath in (b/'TAGUEAMENTO_COMPLETO').rglob('*'):
    if not oldpath.is_file():continue
    rel=oldpath.relative_to(b/'TAGUEAMENTO_COMPLETO')
    if '.git' in rel.parts:continue
    current=r/rel
    if not current.exists():missing.append(str(rel))
    elif current.read_bytes()!=oldpath.read_bytes():changed.append(str(rel))
print('Original files lost:',missing)
print('Modified original files:',changed)
# Check literal local HTML references without executing frontend code.
for rel in ['index.html','admin/index.html','viewer/index.html']:
    path=r/rel
    for ref in re.findall(r'(?:src|href)=["\']([^"\']+)',path.read_text(encoding='utf-8-sig')):
        if ref.startswith(('http:','https:','#','data:')) or '${' in ref:continue
        target=(path.parent/ref.split('?')[0])
        if not target.exists():print('Missing static reference:',rel,ref)
g=['git','-c','safe.directory=H:/TAGUEAMENTO','-C',str(r)]
for name in ['master','origin/master','origin/main']:
    result=subprocess.run(g+['rev-list','--objects',name,'--missing=print'],capture_output=True,text=True)
    print(name,'missing objects:',len(re.findall(r'^\?',result.stdout,re.M)),'exit:',result.returncode)
