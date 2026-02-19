from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables from .env at startup (if present)
load_dotenv()

from app.routes import scan

app = FastAPI(title="InvisiThreat API")

app.include_router(scan.router)

# Ensure models are imported and tables created when the app starts
from app import models  # noqa: F401 - import for side-effects (model registration)
from app.database import Base, engine
Base.metadata.create_all(bind=engine)

# If the `recommendation` column was added to the model after the table
# was created, try to add the column (simple ALTER TABLE) so existing DBs
# used locally or in Docker get updated without a formal migration.
from sqlalchemy import inspect, text
inspector = inspect(engine)
cols = [c['name'] for c in inspector.get_columns('vulnerabilities')] if 'vulnerabilities' in inspector.get_table_names() else []
if 'recommendation' not in cols:
    try:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE vulnerabilities ADD COLUMN recommendation VARCHAR'))
    except Exception:
        # If alter fails, ignore — user can run migrations manually with Alembic
        pass
