from pathlib import Path
import shutil
r=Path(r'H:\TAGCHECK_FASE2_CLEAN')
w=Path(__file__).parent
s=(r/'backend/main.py').read_text(encoding='utf-8')
start=s.index('engine = create_engine')
end=s.index('app = FastAPI()', start)
s=s[:start]+'''if __package__:
    from .models import Base, Company, User, UserCompany, Equipment, DEFAULT_COMPANY_SLUG
    from .migrate_multiempresa import make_engine, migrate
else:
    from models import Base, Company, User, UserCompany, Equipment, DEFAULT_COMPANY_SLUG
    from migrate_multiempresa import make_engine, migrate

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "legacy-admin@tagcheck.invalid").strip().lower()
engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
try:
    MIGRATION = migrate(engine, ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_EMAIL)
except Exception:
    engine.dispose()
    raise RuntimeError("Database migration failed; no automatic destructive repair was attempted") from None
DEFAULT_COMPANY_ID = MIGRATION["default_company_id"]
LEGACY_USER_ID = MIGRATION["legacy_user_id"]

''' + s[end:]
for name in ['models.py','passwords.py','migrate_multiempresa.py']:
    shutil.copyfile(w/name,r/'backend'/name)
(r/'backend/main.py').write_bytes(s.encode('utf-8'))
t=r/'tests/test_stabilization.py'
s=t.read_text(encoding='utf-8').replace('ROOT=Path(__file__).resolve().parents[1]', 'ROOT=Path(__file__).resolve().parents[1]\nimport sys\nsys.path.insert(0, str(ROOT / "backend"))')
t.write_bytes(s.encode('utf-8'))
shutil.copyfile(w/'test_legacy_contract.py',r/'tests/test_legacy_contract.py')
p=r/'backend/requirements.txt'
p.write_bytes((p.read_text().rstrip()+'\nargon2-cffi==25.1.0\nPyJWT==2.13.0\n').encode())
print('Models and additive migration installed; legacy authentication unchanged.')
