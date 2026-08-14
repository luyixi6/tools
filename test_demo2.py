import sys
sys.path.insert(0, '.')
from backend.db import init_db, get_modules, get_scan
from backend.main import _generate_demo_issues
import requests

init_db()

BASE = 'http://127.0.0.1:8000'
r = requests.post(f'{BASE}/api/project/scan', json={'project_root': r'D:\test\test-cpp-project'})
scan_id = r.json()['scan_id']
print('Scan:', scan_id)

import time
time.sleep(2)

modules = get_modules(scan_id)
print('Modules from DB:', [(m['id'], m['name'], m.get('files', [])) for m in modules])

for m in modules:
    try:
        issues = _generate_demo_issues(scan_id, m)
        print(f"  {m['id']}: {len(issues)} issues")
    except Exception as e:
        import traceback
        print(f"  {m['id']}: ERROR - {e}")
        traceback.print_exc()
