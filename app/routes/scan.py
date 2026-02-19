from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import os
from app.services.sast import scan_code, scan_code_with_ai
from app.database import SessionLocal
from app.models import Vulnerability

from app.services.project_scanner import scan_project
from app.services.recommender import generate_recommendation

router = APIRouter()


@router.post("/scan-file")
async def scan_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), include_ai: bool = False):
    """Scan an uploaded file and return findings immediately.

    Recommendations are generated asynchronously in the background and written
    to the database; the initial response contains findings without AI recommendations.
    """
    import traceback

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {e}")
    # Try UTF-8 decode first, fall back to latin-1 or replacement to avoid crashing
    try:
        code = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            code = content.decode("latin-1")
        except Exception:
            code = content.decode("utf-8", errors="replace")

    # Run rule-based scan immediately and return findings promptly
    try:
        if include_ai:
            results = scan_code_with_ai(code)
        else:
            results = scan_code(code)
    except Exception:
        results = []

    # Ensure consistent key naming: use `ai_recommendation` for AI-generated tips
    # and avoid duplicating it as `recommendation` in the immediate JSON response.
    for f in results:
        # If scan_code_with_ai already attached `ai_recommendation`, good.
        # If not, ensure it's at least present as None for consistency.
        if 'ai_recommendation' not in f:
            f['ai_recommendation'] = None
            
        # Remove `recommendation` if it exists to avoid redundancy
        if 'recommendation' in f:
            del f['recommendation']

    # Wrap the rest of the processing so we can return a helpful error locally
    try:
        db = SessionLocal()
        vuln_ids = []
        try:
            for finding in results:
                vuln = Vulnerability(
                    pattern=finding.get("pattern"),
                    severity=finding.get("severity"),
                    count=1,
                    recommendation=None,
                )
                db.add(vuln)
                # Ensure the instance is persisted and has an id before collecting it
                try:
                    db.flush()
                    db.refresh(vuln)
                except Exception:
                    # If refresh/flush fail, continue; id may be available after commit
                    pass
                vuln_ids.append(vuln.id)
            try:
                db.commit()
            except Exception as e:
                # If the DB schema is missing the `recommendation` column (common when
                # the table was created before the field was added), attempt to alter
                # the table to add the column and retry the insert once.
                msg = str(e)
                db.rollback()
                if "no column named recommendation" in msg or "has no column named recommendation" in msg:
                    try:
                        from app.database import engine
                        from sqlalchemy import text
                        # Use a transactional connection and SQLAlchemy text() for DDL
                        with engine.begin() as conn:
                            conn.execute(text('ALTER TABLE vulnerabilities ADD COLUMN recommendation VARCHAR'))
                    except Exception:
                        # If we cannot alter the table, re-raise the original error
                        raise

                    # Retry persistence in a fresh session
                    try:
                        new_db = SessionLocal()
                        new_ids = []
                        for finding in results:
                            v = Vulnerability(
                                pattern=finding.get("pattern"),
                                severity=finding.get("severity"),
                                count=1,
                                recommendation=None,
                            )
                            new_db.add(v)
                        try:
                            new_db.commit()
                        except Exception:
                            new_db.rollback()
                            raise
                        finally:
                            # collect ids
                            for v in new_db.query(Vulnerability).order_by(Vulnerability.id.desc()).limit(len(results)).all()[::-1]:
                                vuln_ids.append(v.id)
                            new_db.close()
                    except Exception:
                        raise
                else:
                    raise
        except Exception:
            # Close DB and surface a controlled error to the client
            db.close()
            raise HTTPException(status_code=500, detail="Failed to persist scan results")
        finally:
            db.close()

        # Schedule background enrichment of recommendations
        try:
            background_tasks.add_task(_enrich_recommendations_background, vuln_ids, results)
        except Exception:
            # If scheduling fails, ignore — we already returned findings
            pass

        # Build summary counts
        critical = sum(1 for f in results if f.get("severity") == "CRITICAL")
        high = sum(1 for f in results if f.get("severity") == "HIGH")
        medium = sum(1 for f in results if f.get("severity") == "MEDIUM")

        summary = {
            "critical": critical,
            "high": high,
            "medium": medium,
            "total": len(results),
        }

        return {"filename": file.filename, "summary": summary, "findings": results}
    except Exception as e:
        tb = traceback.format_exc()
        # For local debugging return the traceback in the response body
        raise HTTPException(status_code=500, detail={"error": str(e), "trace": tb})


def _enrich_recommendations_background(vuln_ids, findings):
    """Background task: persist recommendations on the vulnerabilities.

    If the finding already has an `ai_recommendation` (set by scan_code_with_ai),
    reuse it directly to avoid a redundant LLM call. Otherwise call generate_recommendation.
    """
    db = SessionLocal()
    try:
        for vid, finding in zip(vuln_ids, findings):
            # Prefer recommendation already computed synchronously
            rec = finding.get("ai_recommendation") or finding.get("recommendation")
            if not rec:
                try:
                    rec = generate_recommendation(finding)
                except Exception:
                    rec = None
            if rec:
                try:
                    vuln = db.get(Vulnerability, vid)
                    if vuln:
                        vuln.recommendation = rec
                        db.add(vuln)
                except Exception:
                    pass
        try:
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()



@router.get('/vulnerabilities')
def list_vulnerabilities():
    """Return all stored vulnerabilities with recommendations (if any)."""
    db = SessionLocal()
    try:
        rows = db.query(Vulnerability).all()
        return [
            {
                'id': r.id,
                'pattern': r.pattern,
                'severity': r.severity,
                'count': r.count,
                'recommendation': r.recommendation,
            }
            for r in rows
        ]
    finally:
        db.close()

@router.post("/scan-project")
def scan_project_endpoint(path: str):
    # Validate that the path exists inside the running environment
    if not os.path.exists(path):
        raise HTTPException(
            status_code=400,
            detail=(
                "Path not found: the provided path does not exist inside the running process. "
                "If you run the application in Docker, mount the host folder into the container "
                "or use the file upload endpoint instead."
            ),
        )

    results = scan_project(path)
    for finding in results:
        try:
            rec = generate_recommendation(finding)
            if rec:
                finding["ai_recommendation"] = rec
            else:
                finding["ai_recommendation"] = None
        except Exception:
            finding["ai_recommendation"] = None
            pass

    # also return a summary like the file scanner
    critical = sum(1 for f in results if f["severity"] == "CRITICAL")
    high = sum(1 for f in results if f["severity"] == "HIGH")
    medium = sum(1 for f in results if f["severity"] == "MEDIUM")

    summary = {
        "critical": critical,
        "high": high,
        "medium": medium,
        "total": len(results),
    }

    return {"summary": summary, "findings": results}