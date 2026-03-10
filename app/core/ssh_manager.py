import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.backends import default_backend

# Define paths within the container volume
PRIVATE_KEY_PATH = "config/id_ec"
PUBLIC_KEY_PATH = "config/id_ec.pub"

def generate_ssh_keys():
    """Generates an Elliptic Curve (EC) key pair and saves them to the config volume."""
    
    # 1. Generate Private Key (using the SECP256R1 curve)
    # This replaces rsa.generate_private_key
    key = ec.generate_private_key(
        curve=ec.SECP256R1(),
        backend=default_backend()
    )

    # 2. Serialize Private Key (OpenSSH format)
    # Note: OpenSSH format is required for modern SSH keys
    private_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption()
    )

    # 3. Serialize Public Key (OpenSSH format)
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    )

    # 4. Save to config folder
    # Ensure the directory exists first
    os.makedirs(os.path.dirname(PRIVATE_KEY_PATH), exist_ok=True)

    with open(PRIVATE_KEY_PATH, "wb") as f:
        f.write(private_key)
    
    # Set permissions to 600 (Owner read/write only)
    os.chmod(PRIVATE_KEY_PATH, 0o600)

    with open(PUBLIC_KEY_PATH, "wb") as f:
        f.write(public_key)

    return public_key.decode('utf-8')

def get_public_key():
    """Reads the public key if it exists."""
    if os.path.exists(PUBLIC_KEY_PATH):
        with open(PUBLIC_KEY_PATH, "r") as f:
            return f.read()
    return None