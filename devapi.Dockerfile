# devapi.Dockerfile (replace existing)
FROM python:3.10-slim
WORKDIR /app

# Copy everything (or restrict to needed folders)
COPY . /app

ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates gnupg sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r backend/requirements.txt gunicorn

EXPOSE 5001

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "backend.dev_api_prod:app"]
