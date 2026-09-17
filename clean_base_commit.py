from pathlib import Path
import subprocess, sys
r=Path(r'H:\TAGCHECK_FASE2_CLEAN')
assert not (r/'.git').exists(),'Do not reuse an existing repository'
g=['git','-c','safe.directory=H:/TAGCHECK_FASE2_CLEAN','-C',str(r)]
def run(*args):subprocess.run(g+list(args),check=True)
run('init','-b','fase-2/multiempresa')
run('remote','add','origin','https://github.com/robbertojustinno/TAG.git')
run('add','.')
run('status')
subprocess.run([sys.executable,'-B',r'H:\TAGCHECK\clean_base_verify.py'],check=True)
run('diff','--cached','--stat')
run('commit','-m','chore: base limpa pre fase 2 multiempresa')
assert subprocess.check_output(g+['rev-list','--count','--all']).strip()==b'1'
assert len(subprocess.check_output(g+['rev-list','--parents','-1','HEAD']).split())==1
run('tag','-a','TAGCHECK_FASE2_BASE_LIMPA_2026-09-10','-m','Base limpa e sanitizada para inicio da Fase 2 multiempresa')
run('log','--oneline')
run('status')
run('ls-files')
run('fsck','--full')
print('Confirmed: one root commit with no parents; no imported history.')
