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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure repo root is on path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../'))

from verifier.models import Base, Receipt
from tools.signer import sign_payload
from tools.pdf_receipt import build_pdf_for_receipt
from tools.emailer import send_certificate

# --- Logging configuration ---
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("devapi_prod")

# --- Flask app setup ---
app = Flask(__name__, static_folder="../frontend", static_url_path="/")

# --- Environment variables ---
JWT_SECRET = os.environ.get("DEV_API_JWT_SECRET", "devsecret")
OPERATOR_PIN = os.environ.get("SECUREWIPE_OPERATOR_PIN", "1909")
DATABASE_URL = os.environ.get("VERIFIER_DB_URL", "sqlite:///data/devapi.db")
PRIVATE_KEY = os.environ.get("SIGNING_KEY_PATH", "/app/private_prod.pem")
VERIFIER_URL = os.environ.get("VERIFIER_API_URL", "http://localhost:5000")
RATE_LIMIT_STORAGE = os.environ.get("RATE_LIMIT_STORAGE")  # prefer None so we can detect

# --- Database setup ---
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)
# Create tables if missing
Base.metadata.create_all(bind=engine, checkfirst=True)

# --- Limiter setup: prefer Redis if configured and reachable, otherwise memory ---
def pick_rate_limit_storage(uri: str | None) -> str:
    """
    Validate and return a storage URI for Flask-Limiter.
    If a Redis URI was provided, attempt a quick connection test.
    If the test fails, fallback to memory:// and log a warning.
    """
    if not uri:
        logger.info("RATE_LIMIT_STORAGE not set — using in-memory rate limiting (dev only).")
        return "memory://"

    uri_lower = uri.lower()
    if uri_lower.startswith("redis://") or uri_lower.startswith("rediss://"):
        # Attempt to import redis and ping the server to validate connectivity.
        try:
            import redis as _redis  # type: ignore
            # redis.from_url handles both redis:// and rediss://
            r = _redis.from_url(uri, socket_connect_timeout=3)
            r.ping()  # will raise if cannot connect
            logger.info("Connected to Redis for rate limiting: %s", uri)
            return uri
        except Exception as e:
            logger.warning("Failed to connect to Redis at %s — falling back to in-memory rate limiting. Reason: %s", uri, e)
            return "memory://"
    else:
        # If it's some other supported scheme (like memcached), pass it through.
        logger.info("Using configured rate-limiter storage URI: %s", uri)
        return uri

_storage_uri = pick_rate_limit_storage(RATE_LIMIT_STORAGE)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[os.environ.get("DEV_RATE_LIMIT", "60 per minute")],
    storage_uri=_storage_uri,
)
# bind limiter to app
limiter.init_app(app)

# --- Helper functions ---
def create_jwt(operator="operator"):
    payload = {"operator": operator, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=4)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_jwt(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def require_jwt(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(None, 1)[1]
            data = verify_jwt(token)
            if data:
                request.operator = data.get("operator")
                return f(*args, **kwargs)
        return jsonify({"error": "unauthorized"}), 401

    return wrapper


# --- Routes ---
@app.route("/")
def index():
    return app.send_static_file("index_bootstrap_api.html")


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
    session = SessionLocal()
    try:
        r = Receipt(
            job_id=job_id,
            operator=getattr(request, "operator", "operator"),
            device=json.dumps(p.get("device")),
            method=p.get("method"),
            signature="",
            raw_payload=json.dumps(p),
            status="created",
            email=email,
        )
        session.add(r)
        session.commit()
        logger.info("Created wipe job %s email=%s", job_id, email)
        return jsonify({"status": "created", "job_id": job_id}), 201
    except Exception as e:
        session.rollback()
        logger.exception("DB error creating job")
        return jsonify({"error": "db_error", "detail": str(e)}), 500
    finally:
        session.close()


@app.route("/api/get_job/<job_id>", methods=["GET"])
@require_jwt
def get_job(job_id):
    session = SessionLocal()
    try:
        r = session.query(Receipt).filter(Receipt.job_id == job_id).first()
        if not r:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"job_id": r.job_id, "status": r.status, "device": json.loads(r.device or "{}")})
    finally:
        session.close()


@app.route("/api/report", methods=["POST"])
@require_jwt
@limiter.limit("30 per minute")
def report_result():
    p = request.get_json(force=True) or {}
    job_id = p.get("job_id")
    session = SessionLocal()
    try:
        job = session.query(Receipt).filter(Receipt.job_id == job_id).first()
        if not job:
            return jsonify({"error": "not_found"}), 404

        job.status = p.get("status", "done")
        job.raw_payload = json.dumps(p)
        receipt_json = p
        sig = ""

        # Sign receipt
        try:
            if os.path.exists(PRIVATE_KEY):
                sig = sign_payload(PRIVATE_KEY, receipt_json)
                job.signature = sig
                job.signed_json = json.dumps(receipt_json)
        except Exception:
            logger.exception("Signing failed")

        # Generate PDF
        try:
            pdf_path = build_pdf_for_receipt(receipt_json, sig, job.job_id)
            job.pdf_path = pdf_path
        except Exception:
            logger.exception("PDF generation failed")

        session.add(job)
        session.commit()

        # Send email
        try:
            if job.pdf_path and job.email:
                send_certificate(
                    job.email,
                    f"BitShred Wipe Certificate {job.job_id}",
                    "Attached is your wipe certificate.",
                    job.pdf_path,
                )
        except Exception:
            logger.exception("Email sending failed")

        return jsonify({"status": "ok", "job_id": job.job_id, "signature": sig})
    finally:
        session.close()


if __name__ == "__main__":
    # For local/dev usage we keep flask run mode; in production run under gunicorn
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
