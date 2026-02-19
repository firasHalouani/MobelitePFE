FROM python:3.10-alpine

WORKDIR /app

# Install system dependencies for psycopg2 and other packages
RUN apk add --no-cache gcc musl-dev postgresql-dev libpq

COPY requirements.txt .

# Upgrade pip tools and install requirements
RUN pip install --no-cache-dir --upgrade pip setuptools wheel jaraco.context>=6.1.0 && \
    pip install --no-cache-dir -r requirements.txt

# Remove build-only dependencies
RUN apk del gcc musl-dev postgresql-dev

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
