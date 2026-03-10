import time
import os
import json
import shutil
import subprocess
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from app.core.logger import setup_logging
from app.core.task_manager import run_production_pipeline
from app.core.database import init_db, trim_database
from app.core.ssh_utils import remove_ssh_host_identity

SCHEDULE_PATH = "config/schedule.txt"
FLAG_PATH = "data/run_now.flag"
DELETE_REQUEST_PATH = "data/delete_request.txt"
LEGACY_LIST_PATH = "data/legacy_list.json"
DOWNLOAD_REQ_PATH = "data/download_request.txt"
SHARED_DOWNLOAD_ZONE = "data/transfer_zone"
PUSH_REQ = "data/push_request.json"
PURGE_FLAG = "data/purge_ssh.json"
BACKUP_DIR = os.path.join("data", "geoip-backup")
LEGACY_DIR = "legacy"

last_schedule_mod_time = 0

def check_for_delete_requests():
	"""Checks if the UI left a folder name in delete_request.txt."""
	if os.path.exists(DELETE_REQUEST_PATH):
		try:
			with open(DELETE_REQUEST_PATH, "r") as f:
				folder_to_delete = f.read().strip()
			
			# Security check: Ensure we stay inside the legacy folder
			if folder_to_delete and ".." not in folder_to_delete:

				# Delete the active folderin /legacy
				target = os.path.join("legacy", folder_to_delete)
				if os.path.exists(target):
					logger.info(f"Worker deleting requested folder: {target}")
					shutil.rmtree(target)

				# Delete the persistent zip backup in /data/geoip-backup
				target_zip = os.path.join("data", "geoip-backup", f"{folder_to_delete}.zip")
				if os.path.exists(target_zip):
					logger.info(f"Worker deleteing persistent backup: {target_zip}")
					try:
						os.remove(target_zip)
					except Exception as e:
						logger.error(f"Error removing requested zip: {target_zip}")
			
			# Remove the request file after processing
			os.remove(DELETE_REQUEST_PATH)
			# Update the list immediately so the UI reflects the change
			sync_legacy_folders()
		except Exception as e:
			logger.exception(f"Delete request failed: {e}")

def sync_legacy_folders():
	"""Scans legacy dir, trims based on settings.json, and updates UI."""
	legacy_path = "legacy"
	settings_path = "config/settings.json"
	
	# Default limit if file doesn't exist
	retention_limit = 4
	
	try:
		# Load the dynamic limit from the config file
		if os.path.exists(settings_path):
			with open(settings_path, "r") as f:
				settings = json.load(f)
				retention_limit = settings.get("retention_limit", 4)

		# Trim Ephemeral Legacy Folders
		if os.path.exists(legacy_path):
			folders = [f for f in os.listdir(legacy_path) 
					   if os.path.isdir(os.path.join(legacy_path, f))]			
			folders.sort(reverse=True)
			
			if len(folders) > retention_limit:
				to_delete = folders[retention_limit:]
				for folder in to_delete:
					target = os.path.join(legacy_path, folder)
					logger.info(f"Auto-trim: Removing {target} (Limit: {retention_limit})")
					shutil.rmtree(target)
				
				folders = folders[:retention_limit]
			
			# Update the UI list
			with open(LEGACY_LIST_PATH, "w") as f:
				json.dump(folders, f)

		# Trim the Persistent Backup Zips 
		if os.path.exists(BACKUP_DIR):
			zips = [f for f in os.listdir(BACKUP_DIR) if f.endswith('zip')]
			zips.sort(reverse=True) #YYYYMMDD .zip sorts perfectly chronologically
			if len(zips) > retention_limit:
				for zip_file in zips[retention_limit:]:
					target = os.path.join(BACKUP_DIR, zip_file)
					logger.info(f"Auto-trim: Removing backup {target}")
					os.remove(target)

			
	except Exception as e:
		logger.exception(f"Failed to sync/trim legacy folders: {e}")

def refresh_worker_state(scheduler):
	global last_schedule_mod_time

	# --- Part A: Check for Manual Run ---
	if os.path.exists(FLAG_PATH):
		logger.info(f"Manual trigger detected!")
		try:
			os.remove(FLAG_PATH)
			run_production_pipeline(trigger_type="Manual")
		except Exception as e:
			logger.exception(f"Manual run failed: {e}")

	# --- Part B: Check for Schedule Updates ---
	if os.path.exists(SCHEDULE_PATH):
		try:
			current_mod_time = os.path.getmtime(SCHEDULE_PATH)
			if current_mod_time > last_schedule_mod_time:
				logger.info(f" Schedule change detected! Reloading...")
				
				if scheduler.get_job('scheduled_run'):
					scheduler.remove_job('scheduled_run')
				
				with open(SCHEDULE_PATH, "r") as f:
					c = f.read().strip().split()
					if len(c) == 5:
						scheduler.add_job(
							run_production_pipeline, 'cron', 
							minute=c[0], hour=c[1], day=c[2], 
							month=c[3], day_of_week=c[4],
							id='scheduled_run',
							args=["Scheduled"]
						)
						last_schedule_mod_time = current_mod_time
						logger.info(f"Worker rescheduled: {' '.join(c)}")
		except Exception as e:
			logger.exception(f"Failed to update schedule: {e}")

	# --- Part C: Sync Storage List for UI ---
	sync_legacy_folders()

	# --- Part D: Check for Deletion Flags ---
	check_for_delete_requests()
	
	# --- Part E: Check for Download Requests ---
	check_for_download_requests()

	# --- Part F: Check for Targeted Push Requests ---
	process_manual_push()

def check_for_download_requests():
	"""Moves a requested GeoIP.dat to the shared data folder for the UI to grab."""
	if os.path.exists(DOWNLOAD_REQ_PATH):
		try:
			with open(DOWNLOAD_REQ_PATH, "r") as f:
				folder_name = f.read().strip()
			
			source_file = os.path.join("legacy", folder_name, "GeoIP.dat")
			
			if os.path.exists(source_file):
				# Ensure transfer zone exists
				os.makedirs(SHARED_DOWNLOAD_ZONE, exist_ok=True)
				# Copy to data/transfer_zone/GeoIP_20260226.dat
				dest_file = os.path.join(SHARED_DOWNLOAD_ZONE, f"GeoIP_{folder_name}.dat")
				shutil.copy2(source_file, dest_file)
				logger.info(f"File staged for UI download: {dest_file}")
			
			os.remove(DOWNLOAD_REQ_PATH)
		except Exception as e:
			logger.exception(f"Download staging failed: {e}")

def process_manual_push():
	"""Checks for and executes a targeted manual push request."""
	if os.path.exists(PUSH_REQ):
		try:
			with open(PUSH_REQ, "r") as f:
				data = json.load(f)
			
			# Path construction
			folder_name = data.get("folder")
			server = data.get("server")
			source_file = os.path.join("legacy", folder_name, "GeoIP.dat")
			
			if os.path.exists(source_file):
				logger.info(f"Manual push started: {source_file} -> {server['Host']}")
				
				# SCP command (Using 4096-bit key from /config)
				scp_cmd = [
					"scp", "-i", "config/id_ec",
					"-o", "StrictHostKeyChecking=no",
					"-o", "ConnectTimeout=10",
					source_file,
					f"{server['User']}@{server['Host']}:{server['Path']}"
				]
				
				result = subprocess.run(scp_cmd, capture_output=True, text=True)
				
				# Log results to the Database & run post deployment
				from app.core.database import add_history_entry
				if result.returncode == 0:
					# Run Post-Deploy Command for Manual Push
					post_cmd = server.get("Command")
					cmd_status = ""
					if post_cmd and post_cmd.strip():
						ssh_cmd = [
							"ssh", "-i", "config/id_ec",
							"-o", "StrictHostKeyChecking=no",                            
							"-o", "ConnectTimeout=10",
							f"{server['User']}@{server['Host']}", post_cmd
						]
						cmd_res = subprocess.run(ssh_cmd, capture_output=True, text=True)
						if cmd_res.returncode == 0:
							cmd_status = " + Command Executed"
						else:
							cmd_status = f" (Command Failed: {cmd_res.stderr[:50]})"

					add_history_entry("Manual Push", "Success", f"Pushed {folder_name} to {server['Host']}")
					logger.info(f"Manual push successful.")
				else:
					add_history_entry("Manual Push", "Failed", f"Error on {server['Host']}: {result.stderr.strip()}")
					logger.error(f"Manual push failed: {result.stderr.strip()}")
			else:
				logger.error(f"Manual push failed: Source folder {folder_name} missing.")

			# Clean up the request file
			os.remove(PUSH_REQ)
		except Exception as e:
			logger.exception(f"Manual push processing failed: {e}")

def check_for_purge_request():
	if os.path.exists(PURGE_FLAG):
		try:
			with open(PURGE_FLAG, "r") as f:
				data = json.load(f)
				target = data.get("target")

			if target:
				logger.info(f"Worker picking up purge request for {target}")
				remove_ssh_host_identity(target)
			
			os.remove(PURGE_FLAG)
		except Exception as e:
			logger.exception(f"Error processing purge flasg: {e}")

def execute_remote_command(ssh_client, command):
	"""Runs the validated command on the remote host."""
	if not command or command.strip() == "":
		return True
	
	try:
		print(f"Executing post-deploy command: {command}")
		stdin, stdout, stderr = ssh_client.exec_command(command, timeout=10)
		exit_status = stdout.channel.recv_exit_status()

		if exit_status == 0:
			print("Remote command executed successfully.")
			return True
		else:
			error = stderr.read().decode().strip()
			print(f"Remote command failed (Exit {exit_status}): {error}")
			return False
	except Exception as e:
		print(f"SSH Command Execution Error: {e}")
		return False

def restore_legacy_backups():
	"""Unzips persistent backups into the ephemeral legacy folder on start up."""
	if not os.path.exists(BACKUP_DIR):
		return
	
	try:
		backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip")]
		if backups:
			logger.info(f"Found {len(backups)} backups. Restoring to ephemeral storage...")
			for item in backups:
				date_str = item.replace(".zip", "")
				target_dir = os.path.join(LEGACY_DIR, date_str)
				#Only extract if it dosn't already exists
				if not os.path.exists(target_dir):
					os.makedirs(target_dir, exist_ok=True)
					shutil.unpack_archive(os.path.join(BACKUP_DIR, item), target_dir)
					logger.info(f"Restored folder: {date_str}")
	except Exception as e:
		logger.error(f"Error restoring backups: {e}")

if __name__ == "__main__":
	setup_logging()
	logger = logging.getLogger("WORKER")
	logger.info("Worker Initializing...")
	init_db()
	restore_legacy_backups()
	
	scheduler = BlockingScheduler()

	# The Watcher: Check every 10 seconds for flags, schedules, and storage sync
	scheduler.add_job(
		refresh_worker_state, 
		'interval', 
		seconds=10, 
		args=[scheduler], 
		id='system_watcher'
	)

	scheduler.add_job(trim_database, 'interval', days=7, args=[60])

	logger.info(f"Performing initial state check...")
	refresh_worker_state(scheduler)

	logger.info(f"Worker started. Monitoring for UI signals...")
	try:
		scheduler.start()
	except (KeyboardInterrupt, SystemExit):
		logger.exception("Worker shutting down...")