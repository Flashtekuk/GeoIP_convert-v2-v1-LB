import json
import os
import subprocess
import logging

logger = logging.getLogger("SERVERMANAGER")

SERVERS_FILE = "config/servers.json"

def load_servers():
    """Loads the server list from the config volume and ensures all keys exist."""
    default_server = [
        {"Alias": "Primary-LB", "Host": "10.0.0.1", "Path": "/usr/local/geo/data/", "User": "root", "Command": ""}
    ]

    if os.path.exists(SERVERS_FILE):
        try:
            with open(SERVERS_FILE, "r") as f:
                servers = json.load(f)
            
            # Ensure 'Command' key exists for every server (Legacy fix)
            for s in servers:
                if "Command" not in s:
                    s["Command"] = ""
            return servers
        except Exception as e:
            logger.exception(f"Error loading servers: {e}")
            return default_server
            
    return default_server

def save_servers(server_list):
    """Saves the current server list to the config volume."""
    with open(SERVERS_FILE, "w") as f:
        json.dump(server_list, f, indent=4)

def test_server_connection(server):
    """
    Tests SSH connectivity and directory write permissions.
    Returns: (bool, string) -> (Success/Fail, Message)
    """
    logger.info(f"Testting SSH connection to {server}")
    # -o BatchMode=yes ensures it doesn't hang asking for a password
    # we run 'test -w <path>' to check if the directory is writable
    ssh_cmd = [
        "ssh", "-i", "config/id_ec",
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        f"{server['User']}@{server['Host']}",
        f"test -d {server['Path']} && test -w {server['Path']}"
    ]
    
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Server: {server} connection OK")
            return True, "Connection & Permissions OK"
        elif result.returncode == 1:
            logger.warning(f"Path not found or not writable on host: {server}")
            return False, "Path not found or not writable"
        else:
            # Captures SSH errors like 'Permission denied' or 'Could not resolve hostname'
            error_detail = result.stderr.strip() or "SSH Connection Failed"
            logger.error(f"SSH connection failed: {result.stderr.strip()}")
            return False, error_detail
    except Exception as e:
        logger.error(f"Error from SSH test: {e}")
        return False, str(e)