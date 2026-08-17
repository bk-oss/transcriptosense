import traceback
from argostranslate import package

try:
    available = package.get_available_packages()
    en_fr = [p for p in available if getattr(p, 'from_code', None) == 'en' and getattr(p, 'to_code', None) == 'fr']
    print('found', len(en_fr), 'en->fr available packages')
    if not en_fr:
        print('none')
    else:
        p = en_fr[0]
        print('repr:', repr(p))
        try:
            print('dir:', dir(p))
        except Exception as e:
            print('dir error', e)
        # try to print known attrs
        for attr in ['from_code','to_code','package_name','version','download_url','package_path','id']:
            print(attr, '=>', getattr(p, attr, '<missing>'))
        # if __dict__ available
        try:
            print('__dict__:', p.__dict__)
        except Exception as e:
            print('__dict__ error', e)
except Exception:
    traceback.print_exc()
