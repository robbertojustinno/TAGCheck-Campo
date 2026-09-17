from pathlib import Path
import subprocess, re, hashlib

root = Path(r'H:\TAGUEAMENTO')
git = ['git', '-c', 'safe.directory=H:/TAGUEAMENTO', '-C', str(root)]
mirror = ['git', '--git-dir=H:/TAGCHECK/tagcheck-origin-recovery-20260910.git']

def run(args, **kw):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, **kw).stdout

# Recover exact objects only. No refs, files or existing objects are replaced.
for oid in ['d30f9a20137580eb45a82acc49e6640bfe62bc87', 'c17e96641c8631406dc57dfe66ffe484031c006e']:
    kind = run(mirror + ['cat-file', '-t', oid]).decode().strip()
    data = run(mirror + ['cat-file', kind, oid])
    actual = run(git + ['hash-object', '-w', '-t', kind, '--stdin'], input=data).decode().strip()
    assert actual == oid
    print('Recovered', oid)

def read(rel):
    return (root / rel).read_bytes().decode('utf-8-sig').replace('\r\n', '\n')

def write(rel, data):
    (root / rel).write_bytes(data.encode('utf-8'))

s = read('backend/main.py')
s = s.replace('import os\n', 'import os\nimport secrets\nimport hashlib\nimport hmac\nimport time\n')
start = s.index('DATABASE_URL =')
end = s.index('engine = create_engine', start)
s = s[:start] + '''def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


DATABASE_URL = required_env("DATABASE_URL")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
ADMIN_USERNAME = required_env("ADMIN_USERNAME")
ADMIN_PASSWORD = required_env("ADMIN_PASSWORD")
# Server-only signing key; never return this value to a client.
ADMIN_TOKEN = required_env("ADMIN_TOKEN")
if len(ADMIN_TOKEN) < 32:
    raise RuntimeError("ADMIN_TOKEN must contain at least 32 characters")
CLOUDINARY_CLOUD_NAME = required_env("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = required_env("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = required_env("CLOUDINARY_API_SECRET")
SESSION_TTL_SECONDS = 8 * 60 * 60

''' + s[end:]
s = s.replace('allow_credentials=True', 'allow_credentials=False')
for name in ['CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET']:
    s = s.replace(f'os.getenv("{name}")', name)
start = s.index('def require_admin(')
end = s.index('@app.get("/")', start)
s = s[:start] + '''def session_signature(payload: str) -> str:
    # Password/username changes invalidate sessions, as does signing-key rotation.
    identity = ADMIN_USERNAME + "\\0" + ADMIN_PASSWORD + "\\0" + payload
    return hmac.new(ADMIN_TOKEN.encode(), identity.encode(), hashlib.sha256).hexdigest()


def issue_session() -> str:
    payload = f"{int(time.time()) + SESSION_TTL_SECONDS}.{secrets.token_hex(32)}"
    return f"{payload}.{session_signature(payload)}"


def require_admin(authorization: str = Header(default=None)) -> str:
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise ValueError()
        token = authorization[7:]
        if len(token) > 200:
            raise ValueError()
        expires, nonce, signature = token.split(".")
        payload = f"{expires}.{nonce}"
        if len(nonce) != 64 or not hmac.compare_digest(signature, session_signature(payload)):
            raise ValueError()
        if int(expires) <= int(time.time()):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired session") from None
    return ADMIN_USERNAME


''' + s[end:]
s = s.replace('if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:', 'if not (secrets.compare_digest(username.encode(), ADMIN_USERNAME.encode()) &\n            secrets.compare_digest(password.encode(), ADMIN_PASSWORD.encode())):')
s = s.replace('"token": ADMIN_TOKEN,', '"token": issue_session(),\n        "expires_in": SESSION_TTL_SECONDS,')
# Repair the preexisting invalid function call, keeping master label dimensions.
s = s.replace('min(label_width * 0.75, label_height * 0.70)(label_width * 0.62, label_height * 0.58)', 'min(label_width * 0.75, label_height * 0.70)')
write('backend/main.py', s)

s = read('admin/config.js')
s = re.sub(r"authToken:\s*'[^']*'", "authToken: 'tagcheck_admin_session_v1'", s)
s = s.replace('/api/equipment', '/equipment')
write('admin/config.js', s)
s = read('admin/app.js')
# Authentication already consumes /auth/login. Keep that API and stop persisting
# bearer credentials in localStorage; only the current tab keeps the session.
for method in ['getItem', 'setItem', 'removeItem']:
    for key in ['authToken', 'authUser']:
        s = s.replace(f'localStorage.{method}(CONFIG.STORAGE_KEYS.{key}', f'sessionStorage.{method}(CONFIG.STORAGE_KEYS.{key}')
s = s.replace("const state = {", "// Discard the previous persistent login; require a fresh server-issued session.\nlocalStorage.removeItem('tagcheck_admin_auth_token');\nlocalStorage.removeItem('tagcheck_admin_auth_user');\n\nconst state = {")
# Do not render backend diagnostics to the login UI.
s = s.replace("throw new Error(text || t('loginError'));", "throw new Error(t('loginError'));")
write('admin/app.js', s)

s = read('.gitignore')
for entry in ['.env', '.env.*', '!.env.example', '*.key', '*.pem', '*.pfx', '*.p12', 'credentials*', 'secrets*', 'tokens', 'tokens.*', 'backend/id.txt', '__pycache__/', '*.pyc']:
    if entry not in s.splitlines():
        s = s.rstrip() + '\n' + entry + '\n'
write('.gitignore', s)
write('.env.example', '''# Set these variables in the backend process/deployment environment.
# This file is a template, not automatically loaded by the application.
DATABASE_URL=
ADMIN_USERNAME=
ADMIN_PASSWORD=
# Generate a NEW random server-only signing key (at least 32 characters).
ADMIN_TOKEN=
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
''')
# Keep the private local file intact, remove only the index entry.
run(git + ['rm', '--cached', '--', 'backend/id.txt'])
# Restore missing static assets without replacing any existing file.
logo = root / 'admin/public/logo.png'
if not logo.exists():
    logo.write_bytes(run(mirror + ['show', 'refs/heads/master:admin/public/logo.png']))
for rel, source in [('viewer/public/icons/icon.svg','public/icons/icon.svg'), ('viewer/public/icons/icon-192.png','public/icons/icon-192.png')]:
    if not (root / rel).exists():
        (root / rel).write_bytes((root / source).read_bytes())
print('Sanitization applied; no secret values printed.')
