"""Exercise text/data APIs in a temporary DB. OCR is explicitly stubbed and never executed."""
from pathlib import Path
import os, sys, tempfile, types, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# No OCR engine/model download in this validation: any accidental OCR call fails.
ocr_module=types.ModuleType('main')
def no_ocr(*args,**kwargs):raise AssertionError('OCR must not run in text-only smoke test')
ocr_module.ocr_image_to_sorted_texts=no_ocr
ocr_module.process_pdf=no_ocr
# Load only the actual pure segment_text function by AST; do not import the OCR initializer.
import ast
module_ast=ast.parse((ROOT/'main.py').read_text())
segment=next(n for n in module_ast.body if isinstance(n,ast.FunctionDef) and n.name=='segment_text')
import re
ns={'re':re};exec(compile(ast.Module(body=[segment],type_ignores=[]),str(ROOT/'main.py'),'exec'),ns)
ocr_module.segment_text=ns['segment_text'];sys.modules['main']=ocr_module
sys.modules['openai']=None  # Force offline fallback even if an SDK or .env is present.
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory(prefix='ancient-ocr-validation-') as tmp:
 os.chdir(tmp)
 os.environ.pop('OPENAI_API_KEY',None);os.environ.pop('OPENAI_BASE_URL',None)
 import api_server
 with TestClient(api_server.app) as client:
  r=client.get('/api/health');assert r.status_code==200,(r.status_code,r.text)
  health=r.json()
  r=client.post('/api/records',json={'title':'离线验证记录','original_text':'司马迁记述项羽。项羽在咸阳。','source_type':'manual'})
  assert r.status_code in [200,201],r.text
  record_id=r.json()['id']
  r=client.get(f'/api/records/{record_id}');assert r.status_code==200
  r=client.get('/api/records');assert r.status_code==200 and r.json()['total']==1
  r=client.post('/api/extract',json={'text':'司马迁记述项羽。项羽在咸阳。','chunk_size':1200,'max_chunks':8})
  assert r.status_code==200,r.text
  result={'health':health,'create_read_list_record':'pass','rule_based_extraction':'pass','ocr':'NOT RUN: explicit stub; no OCR or external API','database':'temporary isolated SQLite; no imported user data'}
  print(json.dumps(result,ensure_ascii=False,indent=2))
