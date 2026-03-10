import requests
import re
import logging

logger = logging.getLogger("MAXMIND")

def is_valid_format(key):
    """Regex to check MaxMind API key, before even trying the internet."""
    logger.info(f"checking MaxMind API key format")
    return bool(re.fullmatch(r'[a-zA-Z0-9_-]{16,40}', key.strip()))

def test_connection(key):
    """
    Checks the key against MaxMind without downloading the actual database.
    Uses a HEAD request to verify credentials.
    """

    logger.info(f"Testting connection to MaxMind API with supplied key.")
    # The URL your bash script uses
    test_url = f"https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country&license_key={key}&suffix=tar.gz"
    
    try:
        # allow_redirects=True is important as MaxMind redirects to a storage bucket
        response = requests.head(test_url, allow_redirects=True, timeout=5)
        
        if response.status_code == 200:
            # Check if it's actually a compressed file and not an error page
            logger.info("MaxMind API test returned a 200: test successful")
            content_type = response.headers.get('Content-Type', '')
            if 'gzip' in content_type or 'tar' in content_type or 'octet-stream' in content_type:
                return True, "Success: Key is active and valid!"
            else:
                logger.warning("Connected, but received unexpected file type.")
                return False, "Warning: Connected, but received unexpected file type."
        
        elif response.status_code in [401, 403, 400]:
            logger.error("MaxMind API: Invalid License Key.")
            return False, "Error: Invalid License Key."
        else:
            logger.error(f"MaxMind returned status {response.status_code}")
            return False, f"Error: MaxMind returned status {response.status_code}"
            
    except Exception as e:
        logger.exception(f"Connection failed: {str(e)}")
        return False, f"Connection failed: {str(e)}"