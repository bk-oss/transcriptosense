import traceback
from argostranslate import package

try:
    available = package.get_available_packages()
    en_fr = [p for p in available if getattr(p, 'from_code', None) == 'en' and getattr(p, 'to_code', None) == 'fr']
    if not en_fr:
        print('No en->fr available')
    else:
        p = en_fr[0]
        print('Downloading package via AvailablePackage.download()...')
        fname = p.download()
        print('Downloaded to', fname)
        print('Installing package...')
        package.install_from_path(fname)
        print('Installed package from', fname)
except Exception:
    traceback.print_exc()
