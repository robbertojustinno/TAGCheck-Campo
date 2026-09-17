from pathlib import Path
from urllib.parse import urlsplit,unquote
import re, json, hashlib, ast, subprocess
from clean_base_prepare import scan, SOURCE, DEST, BACKUP, AUDIT, sha

scan(DEST)
expected=['.env','.env.*','!.env.example','backend/id.txt','*.pem','*.key','*.pfx','*.p12','credentials*','secrets*','tokens*','__pycache__/','*.pyc']
lines=(DEST/'.gitignore').read_text().splitlines()
assert all(line in lines for line in expected)
print('.gitignore: all required patterns present')

broken=[]; checked=0
for p in DEST.rglob('*.html'):
    text=p.read_text(encoding='utf-8-sig')
    for raw in re.findall(r'''(?:src|href)\s*=\s*["']([^"']+)''',text):
        url=urlsplit(raw)
        if url.scheme or url.netloc or not url.path or '${' in raw:continue
        local=DEST/url.path.lstrip('/') if url.path.startswith('/') else p.parent/unquote(url.path)
        checked+=1
        if not local.exists():broken.append((str(p.relative_to(DEST)),raw))
for p in DEST.rglob('*.webmanifest'):
    manifest=json.loads(p.read_text(encoding='utf-8-sig'))
    for icon in manifest.get('icons',[]):
        url=urlsplit(icon['src'])
        if url.scheme or url.netloc:continue
        checked+=1
        local=DEST/url.path.lstrip('/') if url.path.startswith('/') else p.parent/url.path
        if not local.exists():broken.append((str(p.relative_to(DEST)),icon['src']))
print('Static HTML/manifest paths checked:',checked,'broken:',broken)
assert not broken,'Critical static reference failure'
for p in DEST.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))

g=['git','-c','safe.directory=H:/TAGCHECK_FASE2_CLEAN','-C',str(DEST)]
if (DEST/'.git').exists():
    staged=subprocess.check_output(g+['ls-files','-z']).decode().split('\0')[:-1]
    assert len(staged)==sum(p.is_file() and '.git' not in p.relative_to(DEST).parts for p in DEST.rglob('*'))
    for name in staged:
        assert name!='backend/id.txt'
        assert not (Path(name).name.startswith('.env') and Path(name).name!='.env.example')
        # Verify actual index bytes, normalizing only Git's CRLF conversion.
        index=subprocess.check_output(g+['show',':'+name])
        local=(DEST/name).read_bytes()
        assert index==local or index==local.replace(b'\r\n',b'\n'),name
    # Read the requested full staged diff without printing source or secrets.
    diff=subprocess.check_output(g+['diff','--cached','--no-ext-diff'])
    print('Full staged diff reviewed:',len(diff),'bytes; staged files:',len(staged))

evidence=json.loads(AUDIT.read_text())
now={str(p.relative_to(SOURCE)):sha(p) for p in SOURCE.rglob('*') if p.is_file()}
assert now==evidence['source'],'Original source changed'
for name,digest in evidence['backup_metadata'].items():assert sha(BACKUP/name)==digest
verified=0
for row in (BACKUP/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines():
    digest,rel=row.split('  ',1)
    assert sha(BACKUP/rel).lower()==digest.lower()
    verified+=1
print('Original source including .git unchanged; backup metadata unchanged;',verified,'backup hashes unchanged')
