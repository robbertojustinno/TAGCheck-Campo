import subprocess, re
g=['git','-c','safe.directory=H:/TAGUEAMENTO','-C','H:/TAGUEAMENTO']
m=['git','--git-dir=H:/TAGCHECK/tagcheck-origin-recovery-20260910.git']
restored=[]
while True:
    result=subprocess.run(g+['fsck','--full'],capture_output=True)
    missing=re.findall(rb'missing (commit|tree|blob|tag) ([0-9a-f]{40})', result.stdout+result.stderr)
    progress=False
    for kind,oid in missing:
        kind,oid=kind.decode(),oid.decode()
        data=subprocess.run(m+['cat-file',kind,oid],capture_output=True)
        if data.returncode: continue
        saved=subprocess.run(g+['hash-object','-w','-t',kind,'--stdin'],input=data.stdout,capture_output=True,check=True).stdout.decode().strip()
        assert saved==oid
        restored.append(oid); progress=True
    if not progress: break
print('Additional objects restored:',len(restored))
print(result.stdout.decode(errors='replace'))
print(result.stderr.decode(errors='replace'))
print('FSCK exit:',result.returncode)
