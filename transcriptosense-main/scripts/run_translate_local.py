import sys, os
sys.path.insert(0, os.getcwd())
from src.api.services.translation_service import translate_text

print('calling translate_text')
res = translate_text('Hello, world!', 'fr')
print('result:', res)
