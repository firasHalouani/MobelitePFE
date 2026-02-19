FROM python:3.10-alpine

WORKDIR /app

# Only install runtime libpq for psycopg2-binary
# We avoid build tools (gcc, postgresql-dev) to prevent build crashes on the runner
RUN apk add --no-cache libpq

COPY requirements.txt .

# Upgrade pip and install requirements. 
# psycopg2-binary should use a musllinux wheel on Alpine 3.10+.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel jaraco.context>=6.1.0 && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
