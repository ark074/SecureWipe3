# verifier.Dockerfile (replace existing)
FROM python:3.10-slim
WORKDIR /app

# Copy verifier package into /app/verifier
COPY ./verifier /app/verifier

# Make sure /app is on Python path so 'import verifier' works
ENV PYTHONPATH=/app

# Install runtime deps and gunicorn
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r verifier/requirements_prod.txt gunicorn

EXPOSE 5000

# Run as WSGI app so python package imports behave correctly
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "verifier.app_prod:app"]
