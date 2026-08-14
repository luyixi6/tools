import sys
sys.path.insert(0, '.')
from backend.db import init_db
from backend.main import _generate_demo_issues

init_db()
module = {'id': 'test', 'files': [r'D:\test\test-cpp-project\src\core\data_processor.cpp']}

try:
    issues = _generate_demo_issues('test_scan', module)
    print('Issues generated:', len(issues))
    for i in issues:
        print(f"  [{i['severity']}] L{i['line_start']}-{i['line_end']}: {i['title']}")
except Exception as e:
    import traceback
    traceback.print_exc()
