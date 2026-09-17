from pathlib import Path
import shutil
r=Path(r'H:\TAGCHECK_FASE2_CLEAN');w=Path(__file__).parent
for name in ['media.py','tenancy.py','migrate_multiempresa.py']:
    shutil.copyfile(w/name,r/'backend'/name)
for name in ['test_multiempresa.py','test_migration.py']:
    shutil.copyfile(w/name,r/'tests'/name)
p=r/'backend/main.py';s=p.read_text(encoding='utf-8')
s=s.replace('    from .admin_api import build_router','    from .admin_api import build_router\n    from .media import upload_photo, photo_url')
s=s.replace('    from admin_api import build_router','    from admin_api import build_router\n    from media import upload_photo, photo_url')
s=s.replace('"photo": item.photo,','"photo": photo_url(item, DEFAULT_COMPANY_ID),')
start=s.index('        result = cloudinary.uploader.upload(')
end=s.index('        item = Equipment(',start)
s=s[:start]+'        image_url = upload_photo(photo.file, _auth.company_id, DEFAULT_COMPANY_ID)\n\n'+s[end:]
start=s.index('            result = cloudinary.uploader.upload(')
end=s.index('\n        db.commit()',start)
s=s[:start]+'            item.photo = upload_photo(photo.file, _auth.company_id, DEFAULT_COMPANY_ID)\n'+s[end:]
p.write_bytes(s.encode('utf-8'))
print('New-company authenticated photo delivery and legacy credential rotation installed.')
