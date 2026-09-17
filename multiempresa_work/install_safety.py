from pathlib import Path
import shutil
r=Path(r'H:\TAGCHECK_FASE2_CLEAN');w=Path(__file__).parent
for rel in ['sw.js','viewer/sw.js']:
    p=r/rel;s=p.read_text(encoding='utf-8')
    s=s.replace("const url = new URL(event.request.url);", """const url = new URL(event.request.url);
  // A shared URL cache must never supply another session's company response.
  if (event.request.headers.has('Authorization')) {
    event.respondWith(fetch(event.request));
    return;
  }""")
    import re
    s=re.sub(r"(const CACHE_NAME = '[^']+)(';)",r"\1-tenant-safe\2",s)
    p.write_bytes(s.encode('utf-8'))
for name in ['test_multiempresa.py','service_worker.test.js','test_browser.py']:
    shutil.copyfile(w/name,r/'tests'/name)
print('Session cache isolation and browser regression installed.')
