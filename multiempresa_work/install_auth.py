from pathlib import Path
import shutil, re
r=Path(r'H:\TAGCHECK_FASE2_CLEAN')
w=Path(__file__).parent
for name in ['tenancy.py','admin_api.py']:
    shutil.copyfile(w/name,r/'backend'/name)
p=r/'backend/main.py'
s=p.read_text(encoding='utf-8')
s=s.replace('Depends, Response','Depends, Response, Request')
s=s.replace('from pydantic import BaseModel','from fastapi.exceptions import RequestValidationError\nfrom fastapi.responses import JSONResponse\nfrom sqlalchemy.exc import IntegrityError')
s=s.replace('from sqlalchemy import create_engine, Column, Integer, String, Text, inspect, text\n','')
s=s.replace('from sqlalchemy.orm import sessionmaker, declarative_base','from sqlalchemy.orm import sessionmaker')
s=s.replace('    from .migrate_multiempresa import make_engine, migrate','    from .migrate_multiempresa import make_engine, migrate\n    from .tenancy import Tenancy, CompanyContext, equipment_query\n    from .admin_api import build_router')
s=s.replace('    from migrate_multiempresa import make_engine, migrate','    from migrate_multiempresa import make_engine, migrate\n    from tenancy import Tenancy, CompanyContext, equipment_query\n    from admin_api import build_router')
s=s.replace('app = FastAPI()', '''auth = Tenancy(SessionLocal, ADMIN_TOKEN, DEFAULT_COMPANY_ID, LEGACY_USER_ID, ADMIN_USERNAME, ADMIN_PASSWORD)
app = FastAPI()
app.include_router(build_router(auth))

@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError):
    # FastAPI's default validation output can echo submitted passwords/tokens.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
    ]})

@app.middleware("http")
async def prevent_private_caching(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
''')
start=s.index('class LoginPayload(')
end=s.index('def build_qr_payload(',start)
s=s[:start]+s[end:]
start=s.index('def session_signature(')
end=s.index('@app.get("/")',start)
s=s[:start]+s[end:]
start=s.index('@app.post("/auth/login")')
end=s.index('@app.post("/equipment")',start)
s=s[:start]+s[end:]
s=s.replace('_auth: str = Depends(require_admin)', '_auth: CompanyContext = Depends(auth.writer)')
s=s.replace('def list_equipment():','def list_equipment(_auth: CompanyContext = Depends(auth.read_context)):')
s=s.replace('def get_by_tag(tag: str):','def get_by_tag(tag: str, _auth: CompanyContext = Depends(auth.read_context)):')
s=s.replace('def get_qr_payload(id: int):','def get_qr_payload(id: int, _auth: CompanyContext = Depends(auth.read_context)):')
s=s.replace('db.query(Equipment)', 'equipment_query(db, _auth)')
s=s.replace('item = Equipment(\n', 'item = Equipment(\n            company_id=_auth.company_id,\n')
s=s.replace('folder="tagcheck/equipments",','folder="tagcheck/equipments" if _auth.company_id == DEFAULT_COMPANY_ID else f"tagcheck/companies/{_auth.company_id}/equipments",')
start=s.index('def delete_equipment(')
end=s.index('):',start)
s=s[:start]+s[start:end].replace('Depends(auth.writer)','Depends(auth.deleter)')+s[end:]
# Do not leak DB statements, connection details or upload provider diagnostics.
s=re.sub(r'    except Exception as e:\n        db.rollback\(\)\n        raise HTTPException\(status_code=500, detail=f"[^\n]+\n', '''    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Equipment conflicts with an existing record") from None
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Equipment operation failed") from None
''',s)
s=re.sub(r'    except Exception as e:\n        raise HTTPException\(status_code=500, detail=f"[^\n]+\n','    except Exception:\n        raise HTTPException(status_code=500, detail="Equipment lookup failed") from None\n',s)
s=s.replace('@app.get("/equipment/pdf", response_class=StreamingResponse)\ndef equipment_pdf_labels():', 'def equipment_pdf_labels(_auth: CompanyContext):')
s+='''

@app.post("/equipment/pdf-access")
def create_pdf_access(_auth: CompanyContext = Depends(auth.current)):
    with SessionLocal() as db:
        user = db.get(User, _auth.user_id)
        link = auth.membership(db, user.id, _auth.company_id)
        return {"token": auth.issue(user, link, purpose="pdf", ttl=120, legacy=_auth.legacy), "expires_in": 120}


@app.get("/equipment/pdf", response_class=StreamingResponse)
def public_or_session_pdf(_auth: CompanyContext = Depends(auth.read_context)):
    return equipment_pdf_labels(_auth)


@app.post("/equipment/pdf", response_class=StreamingResponse)
def temporary_pdf(request: Request, pdf_token: str = Form(..., max_length=8192)):
    context = auth.from_token(pdf_token, purpose="pdf")
    auth.check_company_hint(request, context)
    return equipment_pdf_labels(context)
'''
p.write_bytes(s.encode('utf-8'))

# Minimal admin changes: same rendering and login form, authenticated reads + PDF POST.
p=r/'admin/app.js'
s=p.read_text(encoding='utf-8')
s=s.replace("headers: { Accept: 'application/json' }", "headers: getAuthHeaders({ Accept: 'application/json' })")
start=s.index('async function loginAdmin(')
end=s.index('async function loadItems(', start)
part=s[start:end]
part=part.replace('return await response.json();', '''const result = await response.json();
  if (result.requires_company_selection) {
    throw new Error('Este usuário precisa selecionar uma empresa pela API. A interface será disponibilizada em etapa posterior.');
  }
  return result;''')
s=s[:start]+part+s[end:]
old='''  document.getElementById('pdfButton')?.addEventListener('click', () => {
    window.open(`${CONFIG.API_BASE_URL}/equipment/pdf`, '_blank', 'noopener,noreferrer');
  });'''
new="  document.getElementById('pdfButton')?.addEventListener('click', openEquipmentPdf);"
assert old in s
s=s.replace(old,new)
s+='''

async function openEquipmentPdf() {
  // Open synchronously to preserve the existing new-tab behavior under popup blockers.
  const target = `tagcheck_pdf_${crypto.randomUUID()}`;
  const tab = window.open('about:blank', target);
  if (!tab) return;
  tab.opener = null;
  try {
    const response = await fetchWithTimeout(`${CONFIG.API_BASE_URL}/equipment/pdf-access`, {
      method: 'POST', headers: getAuthHeaders({ Accept: 'application/json' })
    });
    if (!response.ok) throw new Error('Não foi possível gerar o PDF. Entre novamente e tente outra vez.');
    const result = await response.json();
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `${CONFIG.API_BASE_URL}/equipment/pdf`;
    form.target = target;
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'pdf_token';
    input.value = result.token;
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
    form.remove();
  } catch (error) {
    tab.close();
    const feedback = document.getElementById('searchFeedback');
    if (feedback) feedback.textContent = error.message;
  }
}
'''
p.write_bytes(s.encode('utf-8'))
print('Company-scoped authentication, endpoints and PDF access installed.')
