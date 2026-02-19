import sys
from app.services.project_scanner import scan_project

results = scan_project(".")

critical = [f for f in results if f["severity"] == "CRITICAL"]

print("Total findings:", len(results))
print("Critical findings:", len(critical))

if len(critical) > 0:
    print("CRITICAL vulnerabilities detected!")
    sys.exit(1)
else:
    print("No critical vulnerabilities found.")
