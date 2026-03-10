import os
import json
import sqlite3
import pandas as pd
import zipfile
import logging
from datetime import datetime

logger = logging.getLogger("SUPPORT")

def generate_support_report(root_dir, ssh_test_log=None):
    """Gathers high-level system metadata and returns a dictionary."""
    
    # 1. Load Settings
    settings_path = os.path.join(root_dir, "config", "settings.json")
    settings_info = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                settings_info = json.load(f)
        except Exception as e:
            logger.error(f"Could not read settings.json for support: {e}")

    # 2. Security & Identity Checks
    maxmind_installed = os.path.exists(os.path.join(root_dir, "config/license.key")) or \
                        os.path.exists(os.path.join(root_dir, "config/license.enc"))

    ssh_ready = os.path.exists(os.path.join(root_dir, "config/id_ec")) and \
                os.path.exists(os.path.join(root_dir, "config/id_ec.pub"))

    support_data = {
        "report_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "deployment_summary": {
            "strategy": settings_info.get("deployment_mode", "Not Set"),
            "retention_limit": settings_info.get("retention_limit", "Not Set"),
            "maxmind_api_installed": "Yes" if maxmind_installed else "No",
            "ssh_certs_configured": "Yes" if ssh_ready else "No"
        },
        "remote_targets_list": [],
        "cron_schedule": "Not Configured",
        "recent_history_log": []
    }

    if ssh_test_log:
        support_data["last_ssh_test_details"] = ssh_test_log
        summary = "All Passed" if ssh_test_log.get("all_passed") else "Failures Detected"
        support_data["deployment_summary"]["last_ssh_test_summary"] = f"{summary} at {ssh_test_log.get('timestamp')}"

    # 3. Fill in Remote Targets (excluding commands for security if preferred)
    servers_path = os.path.join(root_dir, "config", "servers.json")
    if os.path.exists(servers_path):
        with open(servers_path, "r") as f:
            support_data["remote_targets_list"] = json.load(f)

    # 4. Fill in Schedule
    sched_path = os.path.join(root_dir, "config", "schedule.txt")
    if os.path.exists(sched_path):
        with open(sched_path, "r") as f:
            support_data["cron_schedule"] = f.read().strip()

    # 5. Database Snapshot (Last 10 entries)
    db_path = os.path.join(root_dir, "data", "history.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            query = "SELECT timestamp, trigger, status, size, details FROM task_history ORDER BY timestamp DESC LIMIT 10"
            df = pd.read_sql_query(query, conn)
            support_data["recent_history_log"] = df.to_dict('records') if not df.empty else "No tasks run yet."
            conn.close()
        except Exception as e:
            support_data["recent_history_log"] = f"DB error: {str(e)}"

    return support_data

def create_support_bundle(root_dir, ssh_test_log=None):
    """Creates a physical ZIP bundle containing the report and raw log files."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_name = f"support_bundle_{timestamp}.zip"
    bundle_path = os.path.join(root_dir, "data", bundle_name)
    
    # 1. Generate the JSON report
    report_dict = generate_support_report(root_dir, ssh_test_log)
    temp_json = os.path.join(root_dir, "data", "system_report.json")
    
    with open(temp_json, "w") as f:
        json.dump(report_dict, f, indent=4)

    # 2. Files to include in the ZIP
    files_to_pack = {
        temp_json: "system_report.json",
        os.path.join(root_dir, "data/appliance.log"): "appliance.log",
        os.path.join(root_dir, "config/logger_config.json"): "logger_config.json",
        os.path.join(root_dir, "config/settings.json"): "settings.json"
    }

    # 
    
    try:
        with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for disk_path, arc_name in files_to_pack.items():
                if os.path.exists(disk_path):
                    zipf.write(disk_path, arcname=arc_name)
                    # For extra thoroughness, grab rotated logs too (appliance.log.1, .2, etc)
                    if "appliance.log" in arc_name:
                        for i in range(1, 4):
                            rotated = f"{disk_path}.{i}"
                            if os.path.exists(rotated):
                                zipf.write(rotated, arcname=f"logs/appliance.log.{i}")
        
        logger.info(f"Support bundle created: {bundle_name}")
        return bundle_path
    
    except Exception as e:
        logger.error(f"Failed to create support bundle: {e}")
        return None
    finally:
        # Cleanup temp JSON
        if os.path.exists(temp_json):
            os.remove(temp_json)