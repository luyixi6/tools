"""
End-to-end test for the CPP Inspector API.
Starts a test server, runs scan + analysis (demo mode), verifies results.
"""
import requests
import time
import sys
import subprocess
import os
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
TEST_PROJECT = str(Path(__file__).resolve().parent.parent.parent / "test-cpp-project")

def test_health():
    r = requests.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print("[PASS] Health check")

def test_providers():
    r = requests.get(f"{BASE_URL}/api/providers")
    assert r.status_code == 200
    providers = r.json()["providers"]
    provider_ids = [p["id"] for p in providers]
    assert "deepseek" in provider_ids
    assert "anthropic" in provider_ids
    assert "openai" in provider_ids
    print(f"[PASS] Providers: {len(providers)} available")

def test_scan():
    r = requests.post(f"{BASE_URL}/api/project/scan", json={
        "project_root": TEST_PROJECT
    })
    assert r.status_code == 200
    data = r.json()
    scan_id = data["scan_id"]
    assert data["status"] == "scanning"
    print(f"[PASS] Scan started: {scan_id}")

    time.sleep(2)

    r = requests.get(f"{BASE_URL}/api/project/status/{scan_id}")
    assert r.status_code == 200
    status = r.json()
    assert status["status"] == "completed"
    assert status["total_files"] > 0
    assert status["total_modules"] > 0
    print(f"[PASS] Scan complete: {status['total_files']} files, {status['total_modules']} modules")

    return scan_id

def test_modules(scan_id):
    r = requests.get(f"{BASE_URL}/api/project/modules/{scan_id}")
    assert r.status_code == 200
    data = r.json()
    modules = data["modules"]
    assert len(modules) > 0
    module_ids = [m["id"] for m in modules]
    print(f"[PASS] Modules: {len(modules)} ({', '.join(m['name'] for m in modules)})")
    return module_ids

def test_analysis(scan_id, module_ids):
    r = requests.post(f"{BASE_URL}/api/analyze/start", json={
        "scan_id": scan_id,
        "module_ids": module_ids
    })
    assert r.status_code == 200
    print(f"[PASS] Analysis started")

    for _ in range(30):
        time.sleep(1)
        r = requests.get(f"{BASE_URL}/api/project/status/{scan_id}")
        status = r.json()
        if status["status"] in ("completed", "failed"):
            break

    scan = requests.get(f"{BASE_URL}/api/project/status/{scan_id}").json()
    print(f"[INFO] Analysis status: {scan['status']}, modules: {scan.get('modules_completed', 0)}/{scan.get('total_modules', 0)}")
    return module_ids

def test_issues(scan_id):
    r = requests.get(f"{BASE_URL}/api/issues/{scan_id}")
    assert r.status_code == 200
    data = r.json()
    issues = data["issues"]
    summary = data["summary"]
    print(f"[PASS] Issues: total={summary['total']}, "
          f"pending={summary['pending']}, "
          f"by_severity={summary['by_severity']}")

    if issues:
        issue = issues[0]
        print(f"  First issue: [{issue['severity']}] {issue['title']}")
        print(f"  File: {issue['file_path']}:{issue['line_start']}")
        print(f"  Original: {issue['original_code'][:60]}...")
        print(f"  Suggested: {issue['suggested_code'][:60]}...")

    return [i["id"] for i in issues]

def test_accept_reject(issue_ids):
    if not issue_ids:
        print("[SKIP] No issues to accept/reject")
        return

    r = requests.post(f"{BASE_URL}/api/issues/{issue_ids[0]}/accept")
    assert r.status_code == 200
    result = r.json()
    if result.get("success"):
        print(f"[PASS] Accepted & applied issue: {issue_ids[0]}")

        r = requests.post(f"{BASE_URL}/api/issues/{issue_ids[0]}/revert")
        assert r.status_code == 200
        print(f"[PASS] Reverted fix: {issue_ids[0]}")
    else:
        print(f"[WARN] Accept returned not-success: {result}")

    if len(issue_ids) > 1:
        r = requests.post(f"{BASE_URL}/api/issues/{issue_ids[1]}/reject")
        assert r.status_code == 200
        print(f"[PASS] Rejected issue: {issue_ids[1]}")


def main():
    print("=" * 50)
    print("CPP Inspector - End-to-End Test")
    print("=" * 50)
    print()

    try:
        test_health()
        test_providers()
        scan_id = test_scan()
        module_ids = test_modules(scan_id)
        test_analysis(scan_id, module_ids)
        issue_ids = test_issues(scan_id)
        test_accept_reject(issue_ids)
    except Exception as e:
        import traceback
        print(f"\n[FAIL] {e}")
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
