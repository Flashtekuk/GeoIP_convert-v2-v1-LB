import os
import subprocess
import json
import logging
import shutil
from datetime import datetime
from app.core.security import decrypt_license
from app.core.database import log_task
from app.core.server_manager import load_servers

logger = logging.getLogger("TASKMANAGER")

def run_production_pipeline(trigger_type="Scheduled"):
    date_str = datetime.now().strftime("%Y%m%d")
    base_dir = os.path.abspath(os.getcwd())
    legacy_dir = os.path.join(base_dir, "legacy")
    dated_folder = os.path.join(legacy_dir, date_str)
    output_file = os.path.join(dated_folder, "GeoIP.dat")
    settings_path = os.path.join(base_dir, "config", "settings.json")

    try:
        # 1. Check if the work is already done for today
        skip_bash = False
        if os.path.exists(output_file):
            logger.info(f"Found existing build for today: {output_file}. Skipping Bash script.")
            skip_bash = True

        # 2. Get Deployment Mode
        deployment_mode = "Remote Only"
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                deployment_mode = json.load(f).get("deployment_mode", "Remote Only")

        # 3. Only run Bash if we don't have today's file
        if not skip_bash:
            license_key = decrypt_license()
            logger.info(f"Starting Bash script in {legacy_dir}...")
            
            result = subprocess.run(
                ["/bin/bash", "./geoip_convert-v2-v1.sh", license_key, "ProdBuild"], 
                cwd=legacy_dir, capture_output=True, text=True
            )

            if result.returncode != 0:
                error_msg = f"Bash Error: {result.stderr.strip()}"
                log_task(trigger_type, 'Failed', "0 MB", error_msg)
                return f"Error: {error_msg}"
            
            backup_legacy_folder(date_str)

        # 4. Deployment Logic
        if os.path.exists(output_file):
            file_size_bytes = os.path.getsize(output_file)
            size_mb = f"{round(file_size_bytes / (1024 * 1024), 2)} MB"
            
            all_success = True
            if deployment_mode != "Local Only":
                servers = load_servers()
                for server in servers:
                    try:
                        deploy_to_server(server, output_file)
                    except Exception as e:
                        logger.exception(f"Deploy failed to {server['Host']}: {e}")
                        all_success = False
            
            # Log status
            status = 'Success' if all_success else 'Partial'
            log_msg = f"Mode: {deployment_mode} | {date_str}"
            if skip_bash:
                log_msg += " (Used existing disk data)"
                
            log_task(trigger_type, status, size_mb, log_msg)
            return status
        else:
            raise FileNotFoundError(f"Pipeline error: {output_file} not found.")

    except Exception as e:
        logger.exception(f"Exception: {str(e)}")
        log_task(trigger_type, 'Failed', "N/A", str(e))
        return f"Error: {str(e)}"

def deploy_to_server(server, local_path):
    logger.info(f"Attempting SCP to {server['Host']}...")

    # Perform the File Transfer
    cmd = [
        "scp", "-i", "config/id_ec", 
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10", # Don't hang forever
        local_path, f"{server['User']}@{server['Host']}:{server['Path']}GeoIP.dat"
    ]

    # Capture output so we see the actual SSH error in our logs
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"SCP Failed to {server['Host']}: {result.stderr}")
    
    logger.info(f"SCP to {server['Host']} successful.")

    # Execute Post-Deployment Command (if it exists)
    post_cmd = server.get("Command")
    if post_cmd and post_cmd.strip():
        logger.info(f"Running Post-Deploy Command on {server['Host']}: {post_cmd}")

        ssh_cmd = [
            "ssh", "-i", "config/id_ec",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            f"{server['User']}@{server['Host']}", post_cmd
        ]

        cmd_result = subprocess.run(ssh_cmd, capture_output=True, text=True)

        if cmd_result.returncode != 0:
            logger.error(f"Command failed on {server['Host']}: {cmd_result.stderr.strip()} ")
        else:
            logger.info(f"Command successful on {server['Host']}.")

def backup_legacy_folder(date_str):
    """Zips the newly created GeoIP folder and saves it to the persistent volume."""
    source_dir = os.path.join("legacy", date_str)
    backup_dir = os.path.join("data", "geoip-backup")

    os.makedirs(backup_dir, exist_ok=True)

    archive_base_path = os.path.join(backup_dir, date_str)

    try:
        shutil.make_archive(archive_base_path, 'zip', source_dir)
        logger.info(f"Back up {date_str} to persistent storage.")
    except Exception as e:
        logger.error(f"Failed to backup {date_str}: {e}")