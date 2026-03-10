import subprocess
import os
import logging

def remove_ssh_host_identity(target):
    """
    Purges a host from the local known_hosts file.
    Works for both IP address and Hostname. 
    """
    # Standard path for Docker containers running as root 
    known_hosts_path = "/root/.ssh/known_hosts"

    if not os.path.exists(known_hosts_path):
        return True # Nothing to purge
    
    try:
        # -R removes the host identity from the file
        result = subprocess.run(
            ['ssh-keygen', '-f', known_hosts_path, '-R', target],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logging.info(f"Successfully purged {target} from {known_hosts_path}")
            return True
        return False
    except Exception as e:
        logging.error(f"Failed to purge {target}: {e}")
        return False
    
def validate_command(command):
    """
    Validates the remote command against a deny-list of dangerous keywords.
    """
    if not command:
        return True, ""
    
    # Strictly forbidden keywords/pattens 
    deny_list = [
        "rm -rf", "useradd", "usermod", "visudo", "passwd",
        "mkfs", "dd", "> /dev/", "chmod", "chown", "shutdown", "reboot"
    ]

    # Check for piping or redirection which can bypass simple checks
    if ";" in command or "&&" in command or "|" in command:
        return False, "Chained commands (; && |) are disabled for security."
    
    for forbidden in deny_list:
        if forbidden in command.lower():
            return False, f"Security Violationi: '{forbidden}' is not allowed."
        
    return True, "Valid"