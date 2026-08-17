import site
import os
import glob
import shutil

print('site-packages dirs:', site.getsitepackages())
removed = []
for d in site.getsitepackages():
    # Common candidates
    candidates = glob.glob(os.path.join(d, 'torchcodec*')) + glob.glob(os.path.join(d, '*torchcodec*')) + glob.glob(os.path.join(d, 'libtorchcodec_core*.dll'))
    for p in candidates:
        try:
            if os.path.isdir(p):
                print('Removing directory:', p)
                shutil.rmtree(p)
                removed.append(p)
            elif os.path.isfile(p):
                print('Removing file:', p)
                os.remove(p)
                removed.append(p)
        except Exception as e:
            print('Failed to remove', p, '-', e)

if not removed:
    print('No torchcodec artifacts found in site-packages.')
else:
    print('Removed artifacts:')
    for r in removed:
        print(' -', r)
print('Cleanup complete.')
