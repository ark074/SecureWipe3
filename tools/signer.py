import json, binascii
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

def sign_payload(private_key_path: str, payload: dict) -> str:
    with open(private_key_path, 'rb') as f:
        key_data = f.read()
    priv = serialization.load_pem_private_key(key_data, password=None, backend=default_backend())
    payload_bytes = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
    sig = priv.sign(payload_bytes, padding.PKCS1v15(), hashes.SHA256())
    return binascii.hexlify(sig).decode()
