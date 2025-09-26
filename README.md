SecureWipe - Production Complete
================================

This package is a production-oriented prototype for BitShred SecureWipe.
It includes backend API, verifier, frontend, agent stubs, and deployment manifests.

IMPORTANT:
- The included agent scripts are safe stubs and **do not** perform destructive wipes by default.
- Always test with dry-run before attempting a real wipe on hardware.
- Replace the provided dev keys with secure production keys and store them in a secret manager.

Quick local test (without Docker):
1. Create virtualenv and install dependencies:
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   pip install -r verifier/requirements_prod.txt

2. Create .env from .env.example and set SIGNING_KEY_PATH to the path of private_prod.pem
3. Run verifier:
   python3 verifier/app_prod.py
4. Run dev API:
   python3 backend/dev_api_prod.py
5. Open frontend: http://localhost:5001/

Docker quick test:
1. Place private_prod.pem and public.pem in repo root (or bind-mount). Update .env accordingly.
2. docker compose up --build
3. Open https://localhost:8443 (nginx proxy)

Security checklist:
- Use HTTPS in production (Render provides TLS)
- Use secure signing keys (rotate regularly)
- Use Redis for limiter in production
- Ensure agents are run locally with user consent and proper privileges
