"""Legacy public photos remain intact; new-company uploads require authenticated delivery."""
import json
import time
import cloudinary.uploader
import cloudinary.utils

PREFIX = 'cloudinary-authenticated:'

def upload_photo(file, company_id, default_company_id):
    if company_id == default_company_id:
        result = cloudinary.uploader.upload(file, folder='tagcheck/equipments', resource_type='image')
        url = result.get('secure_url')
        if not url:
            raise ValueError('Upload did not return a photo')
        return url
    result = cloudinary.uploader.upload(file, folder=f'tagcheck/companies/{company_id}/equipments',
                                        resource_type='image', type='authenticated')
    if result.get('type') != 'authenticated' or not result.get('public_id') or not result.get('format'):
        raise ValueError('Upload did not confirm authenticated delivery')
    return PREFIX + json.dumps({'company_id':company_id,'public_id':result['public_id'],'format':result['format']},separators=(',',':'))

def photo_url(item, default_company_id):
    if item.company_id == default_company_id and not item.photo.startswith(PREFIX):
        return item.photo
    if not item.photo.startswith(PREFIX):
        # Do not publish legacy/public URLs manually inserted under a private tenant.
        return None
    try:
        reference = json.loads(item.photo[len(PREFIX):])
        if reference['company_id'] != item.company_id:
            return None
        return cloudinary.utils.private_download_url(reference['public_id'], reference['format'],
                type='authenticated', resource_type='image', expires_at=int(time.time())+120, attachment=False)
    except (ValueError, KeyError, TypeError):
        return None
