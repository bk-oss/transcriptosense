import traceback
try:
    from argostranslate import package, translate

    installed = package.get_installed_packages()
    print('installed packages:', [(p.from_code, p.to_code, getattr(p, 'package_path', None)) for p in installed])
    available = package.get_available_packages()
    print('available count:', len(available))
    en_fr = [p for p in available if getattr(p, 'from_code', None) == 'en' and getattr(p, 'to_code', None) == 'fr']
    print('available en->fr:', len(en_fr))
    if en_fr:
        print('example url:', en_fr[0].download_url)
except Exception:
    traceback.print_exc()
