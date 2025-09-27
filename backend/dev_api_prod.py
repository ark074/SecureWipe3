#!/usr/bin/env python3
import os
import sys
import json
import logging
import datetime
import jwt
import time
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from mongoengine import connect
from verifier.models import Receipt

# Ensure repo root is on path (already done by project layout, but keep for safety)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../'))

# Basic logging
logger = logging.getLogger("devapi")
logging.basicConfig(level=logging.INFO)

# Config from env
MONGO_URL = os.environ.get("MONGO_URL", os.environ.get("VERIFIER_DB_URL", "mongodb://localhost:27017/securewipe"))
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
OPERATOR_PIN = os.environ.get("OPERATOR_PIN", "1234")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "")
EMAILER_API_KEY = os.environ.get("EMAILER_API_KEY", "")

# Connect to MongoDB
try:
    # If MONGO_URL is a full connection URI, pass as host
    connect(host=MONGO_URL)
    logger.info("Connected to MongoDB at %s", MONGO_URL)
except Exception as e:
    logger.exception("Failed to connect to MongoDB: %s", e)
    raise

app = Flask(__name__)

RATE_LIMIT_STORAGE = os.environ.get("RATE_LIMIT_STORAGE", "")

def pick_rate_limit_storage(uri):
    from urllib.parse import urlparse
    if not uri:
        return "memory://"
    parsed = urlparse(uri)
    if parsed.scheme in ("redis", "rediss"):
        # Validate by trying to import redis client
        try:
            import redis
            r = redis.from_url(uri)
            r.ping()
            logger.info("Connected to Redis for rate limiting: %s", uri)
            return uri
        except Exception as e:
            logger.warning("Failed to connect to Redis at %s — falling back to in-memory rate limiting. Reason: %s", uri, e)
            return "memory://"
    else:
        logger.info("Using configured rate-limiter storage URI: %s", uri)
        return uri

_storage_uri = pick_rate_limit_storage(RATE_LIMIT_STORAGE)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[os.environ.get("DEV_RATE_LIMIT", "60 per minute")],
    storage_uri=_storage_uri
)

# Simple JWT helpers
def create_jwt(role):
    payload = {"role": role, "iat": int(time.time())}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def require_jwt(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = None
        if auth.startswith("Bearer "):
            token = auth.split(None, 1)[1]
        if not token:
            return jsonify({"error": "missing_token"}), 401
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            request.jwt_payload = payload
        except Exception:
            return jsonify({"error": "invalid_token"}), 401
        return fn(*args, **kwargs)
    return wrapper

# --- Utilities that previously used SQLAlchemy models are adapted to mongoengine ---

# Placeholder implementations for signing, pdf generation and email sending.
# Keep existing function names so other modules calling them keep working.
def sign_payload(private_key_pem, payload_json):
    # Implement actual cryptographic signing as required by project.
    # For now, return a simple deterministic signature for testing.
    import hashlib
    return hashlib.sha256((private_key_pem or "") + json.dumps(payload_json, sort_keys=True)).hexdigest()

def build_pdf_for_receipt(receipt_json, signature, job_id):
    # Create a simple PDF file or placeholder path. The real project likely uses reportlab/weasyprint.
    # For now, create a small text file to simulate a pdf path.
    out_dir = os.path.join(os.path.dirname(__file__), "../static/pdfs")
    os.makedirs(out_dir, exist_ok=True)
    fname = f"receipt-{job_id}.txt"
    path = os.path.join(out_dir, fname)
    with open(path, "w") as f:
        f.write("Receipt for job: " + job_id + "\n")
        f.write(json.dumps(receipt_json, indent=2))
        f.write("\nSignature: " + signature)
    return path

def send_receipt_email(to_email, subject, body, attachment_path=None):
    # Implement real email sending using configured EMAILER_API_KEY or SMTP.
    logger.info("Pretend-sending email to %s subj=%s attachment=%s", to_email, subject, attachment_path)
    return True

# --- Routes ---
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json(force=True) or {}
    if data.get("pin") == OPERATOR_PIN:
        token = create_jwt("operator")
        return jsonify({"token": token})
    return jsonify({"error": "invalid_credentials"}), 401

@app.route("/api/create_job", methods=["POST"])
@require_jwt
@limiter.limit("10 per minute")
def create_job():
    p = request.get_json(force=True) or {}
    email = p.get("email")
    if not p.get("confirm"):
        return jsonify({"error": "confirmation_required"}), 400
    if not email:
        return jsonify({"error": "email_required"}), 400

    job_id = p.get("job_id") or f"job-{int(time.time())}"
    try:
        r = Receipt(
            job_id=job_id,
            operator=p.get("operator"),
            device=p.get("device"),
            method=p.get("method"),
            timestamp=datetime.datetime.utcnow(),
            signature="",
            signed_json="",
            raw_payload=json.dumps(p),
            status="created",
            email=email,
        )
        r.save()
        logger.info("Created wipe job %s email=%s", job_id, email)
        return jsonify({"status": "created", "job_id": job_id}), 201
    except Exception as e:
        logger.exception("DB error creating job")
        return jsonify({"error": "db_error", "detail": str(e)}), 500

@app.route("/api/report", methods=["POST"])
@require_jwt
@limiter.limit("30 per minute")
def report_result():
    p = request.get_json(force=True) or {}
    job_id = p.get("job_id")
    try:
        job = Receipt.objects(job_id=job_id).first()
        if not job:
            return jsonify({"error": "not_found"}), 404

        job.status = p.get("status", "done")
        job.raw_payload = json.dumps(p)
        receipt_json = p

        # Sign payload and generate PDF
        try:
            sig = sign_payload(PRIVATE_KEY, receipt_json)
            job.signature = sig
            job.signed_json = json.dumps(receipt_json)
        except Exception:
            logger.exception("Signing failed")

        try:
            pdf_path = build_pdf_for_receipt(receipt_json, sig, job_id)
            job.pdf_path = pdf_path
        except Exception:
            logger.exception("PDF generation failed")

        job.save()
        return jsonify({"status": "ok", "job_id": job_id, "signature": job.signature})
    except Exception as e:
        logger.exception("DB error updating job")
        return jsonify({"error": "db_error", "detail": str(e)}), 500

@app.route("/api/send", methods=["POST"])
@require_jwt
@limiter.limit("10 per minute")
def send_receipt():
    p = request.get_json(force=True) or {}
    job_id = p.get("job_id")
    try:
        job = Receipt.objects(job_id=job_id).first()
        if not job:
            return jsonify({"error": "not_found"}), 404

        try:
            # send email
            send_receipt_email(
                job.email,
                "Your wipe certificate",
                "Attached is your wipe certificate.",
                job.pdf_path,
            )
        except Exception:
            logger.exception("Email sending failed")

        return jsonify({"status": "ok", "job_id": job.job_id, "signature": job.signature})
    except Exception as e:
        logger.exception("DB error sending job")
        return jsonify({"error": "db_error", "detail": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
