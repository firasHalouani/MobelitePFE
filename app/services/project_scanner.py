import os
from app.services.sast import scan_code

def scan_project(folder_path: str):
    all_findings = []

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        code = f.read()
                except UnicodeDecodeError:
                    try:
                        with open(file_path, "r", encoding="latin-1") as f:
                            code = f.read()
                    except Exception:
                        continue  # skip unreadable files
                except Exception:
                    continue  # skip files we can't open

                findings = scan_code(code)

                for finding in findings:
                    finding["file"] = file_path

                all_findings.extend(findings)

    return all_findings
