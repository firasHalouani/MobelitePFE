FROM python:3.10-alpine

WORKDIR /app

# Minimal runtime dependency for database support (replaces postgresql-dev)
RUN apk add --no-cache libpq

COPY requirements.txt .

# Standard upgrade and requirements installation
# psycopg2-binary will install via musllinux wheels on Alpine
RUN pip install --no-cache-dir --upgrade pip setuptools wheel jaraco.context>=6.1.0 && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
