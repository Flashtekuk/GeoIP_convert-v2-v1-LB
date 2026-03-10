import os
import re
from cryptography.fernet import Fernet

KEY_PATH = "config/.master.key"
LICENSE_FILE = "config/license.enc"

# Master key function 
def get_master_key():
    key_path = "config/.master.key"
    if not os.path.exists(key_path):
        key = Fernet.generate_key()
        with open(key_path, "wb") as key_file:
            key_file.write(key)
    with open(key_path,"rb") as key_file:
        return key_file.read()

# Encryption and decryption functions
def encrypt_license(api_key: str):
    f = Fernet(get_master_key())
    encrypted_data = f.encrypt(api_key.encode())
    with open("config/license.enc", "wb") as f_out:
        f_out.write(encrypted_data)

def decrypt_license():
    license_path = "config/license.enc"
    if not os.path.exists(license_path):
        return None
    f = Fernet(get_master_key())
    with open(license_path, "rb") as f_in:
        return f.decrypt(f_in.read()).decode()
    
def check_licence_status():
    """Checks if a valid, non-empty license key is actually stored."""
    if not os.path.exists(KEY_PATH) or not os.path.exists(LICENSE_FILE):
        return False    
    try:
        # Try to decrypt the key
        decrypted_key = decrypt_license()
        
        # A valid status requires the key to exist AND not be blank
        if decrypted_key and len(decrypted_key.strip()) > 0:
            return True
        return False
    except Exception:
        # If decryption fails (corrupt key, etc.), it's not a valid status
        return False

def check_schedule_status(SCHEDULE_FILE):
    """Returns True if the schedule file exists"""
    return os.path.exists(SCHEDULE_FILE)

def is_valid_format(key):
    # MaxMind keys are typically 16 characters alphanumeric
    # Adjust the regex if your specific key type differs
    pattern = r'^[a-zA-Z0-9]{16}$'
    return re.match(pattern, key) is not None