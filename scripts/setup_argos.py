import sys, subprocess, os

print('Ensuring argostranslate is installed...')
try:
    import argostranslate.package
    import argostranslate.translate
    print('argostranslate already installed')
except Exception:
    print('Installing argostranslate via pip...')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'argostranslate'])

# Now try to install English->French package if available
try:
    import requests
    from argostranslate import package, translate
    print('Fetching available Argos packages...')
    available = package.get_available_packages()
    en_fr = None
    for pkg in available:
        if getattr(pkg, 'from_code', None) == 'en' and getattr(pkg, 'to_code', None) == 'fr':
            en_fr = pkg
            break
    if en_fr is None:
        print('No en->fr package found in available list. Listing first 10 packages:')
        for p in available[:10]:
            print(p)
        print('You can manually download packages from https://github.com/argosopentech/argos-models/releases')
    else:
        print('Downloading en->fr package from', en_fr.download_url)
        r = requests.get(en_fr.download_url)
        fname = 'en_fr.argosmodel'
        with open(fname, 'wb') as f:
            f.write(r.content)
        print('Installing package', fname)
        package.install_from_path(fname)
        print('Installed en->fr package')
except Exception as e:
    print('Argos package install failed:', e)
    print('You can manually install argostranslate and argos models. See README or https://github.com/argosopentech/argos-translate')
