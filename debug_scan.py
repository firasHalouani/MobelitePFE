from app.services.project_scanner import scan_project
import os

results = scan_project(".")
for f in results:
    if "venv" in f['file'] or ".git" in f['file'] or "__pycache__" in f['file']:
        continue
    print(f"{f['severity']} | {f['file']} | L{f['line']} | {f['code']}")
