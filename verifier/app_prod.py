#!/usr/bin/env python3
import os
import json
import logging
from flask import Flask, request, jsonify, send_file
from functools import wraps
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from mongoengine import connect, Document, StringField, DateTimeField, IntField
from datetime import datetime

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("verifier_prod")

# --- Flask App ---
app = Flask(__name__)

# --- Environment Variables ---
DATABASE_URL = os.environ.get(
    "VERIFIER_DB_URL",
    "mongodb://localhost:27017/securewipe"  # fallback for local dev
)
VERIFIER_API_KEY = os.environ.get("VERIFIER_API_KEY", "changeme")
VERIFIER_PUBKEY_PATH = os.environ.get("VERIFIER_PUBKEY_PATH", "/app/public.pem")
RATE_LIMIT_STORAGE = os.environ.get("VERIFIER_RATE_LIMIT_STORAGE", "redis://securewipe-redis:6379/0")
RATE_LIMIT_DEFAULT = os.environ.get("VERIFIER_RATE_LIMIT", "60 per minute")

# --- Database Setup ---
try:
    connect(host=DATABASE_URL)
    logger.info(f"Connected to MongoDB at {DATABASE_URL}")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# --- Models (MongoEngine) ---
class Receipt(Document):
    meta = {"collection": "receipts"}
    id = IntField(primary_key=True)
    job_id = StringField(required=True)
    pdf_path = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)

# --- Limiter Setup (with Redis fallback) ---
def pick_rate_limit_storage():
    try:
        if RATE_LIMIT_STORAGE.startswith("redis://"):
            import redis
            r = redis.Redis.from_url(RATE_LIMIT_STORAGE)
            r.ping()
            logger.info("Connected to Redis for rate limiting: %s", RATE_LIMIT_STORAGE)
            return RATE_LIMIT_STORAGE
    except Exception as e:
        logger.warning("Redis not available for limiter, falling back to memory: %s", e)
    return "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[RATE_LIMIT_DEFAULT],
    storage_uri=pick_rate_limit_storage(),
)
limiter.init_app(app)

# --- API Key Auth ---
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = None
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            key = auth.split(None, 1)[1]
        if not key:
            key = request.headers.get("X-API-KEY", None)
        if not key or key != VERIFIER_API_KEY:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# --- Routes ---
@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})

@app.route("/receipts/<int:rid>.pdf", methods=["GET"])
@require_api_key
def get_receipt_pdf(rid):
    r = Receipt.objects(id=rid).first()
    if not r or not r.pdf_path:
        return jsonify({"error": "not_found"}), 404
    if not os.path.exists(r.pdf_path):
        return jsonify({"error": "not_found"}), 404
    return send_file(
        r.pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"securewipe_{r.job_id}.pdf",
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
