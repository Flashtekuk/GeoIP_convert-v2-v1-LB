import os
import streamlit as st
import streamlit_authenticator as stauth
import yaml
import pandas as pd
import sqlite3
import json
import shutil
import time
from croniter import croniter
from datetime import datetime
from yaml.loader import SafeLoader
from app.core.logger import get_ui_logger
from app.core.security import encrypt_license, check_licence_status, check_schedule_status, is_valid_format
from app.core.ssh_manager import generate_ssh_keys, get_public_key
from app.core.server_manager import load_servers, save_servers, test_server_connection
from app.core.database import clear_entire_database
from app.core.support import create_support_bundle
from app.core.maxmind import is_valid_format, test_connection
from app.core.ssh_utils import validate_command
from app.core.ssh_utils import remove_ssh_host_identity


# Variables
VERSION_NUMBER = "V1.1.3"

logger = get_ui_logger()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "LB-Flat-White-RGB.png")
SETTINGS_PATH = "config/settings.json"
LIST_PATH = "data/legacy_list.json"
SCHEDULE_FILE = "config/schedule.txt"
DB_PATH = "data/history.db"



# 1. Page Config
st.set_page_config(page_title="GeoIP Tool", layout="wide")



# 2. Load Credentials from the Volume-Mapped Config Folder
auth_file = 'config/auth.yaml'

if not os.path.exists(auth_file):
    st.error(f"Configuration file not found at {auth_file}. Please ensure the volume is mapped.")
    st.stop()

with open(auth_file) as file:
    config = yaml.load(file, Loader=SafeLoader)

# 3. Initialize Authenticator
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# 4. Render Login
authenticator.login(location='main')

# 5. Handle Authentication State
if st.session_state["authentication_status"]:

    # --- SIDEBAR CONSTRUCTION ---
    with st.sidebar:
        # 1. Logo Section
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width="content")
        else:
            st.error(f"Logo Missing: {LOGO_PATH}") # Temporary debug view
        
        # 2. Welcome & Identity
        st.title(f"Welcome {st.session_state['name']}")
        st.divider()

        # 3. System Health Metrics
        st.subheader("📊 System Health:")
        
        # Worker Heartbeat Check
 
        if os.path.exists(LIST_PATH):
            mtime = os.path.getmtime(LIST_PATH)
            is_online = (time.time() - mtime) < 30
            status_color = "green" if is_online else "red"
            status_text = "Online" if is_online else "Offline"
            st.markdown(f"**Worker:** :{status_color}[{status_text}]")
        else:
            st.markdown("**Worker:** :orange[Initializing]")

        # Database Metrics
        DB_PATH = "data/history.db"
        if os.path.exists(DB_PATH):
            try:
                conn = sqlite3.connect(DB_PATH)
                count = conn.execute("SELECT COUNT(*) FROM task_history").fetchone()[0]
                conn.close()
                st.markdown(f"**History:** {count} records")
            except: pass

        # Schedule Metric
        if os.path.exists("config/schedule.txt"):
            with open("config/schedule.txt", "r") as f:
                cron_str = f.read().strip()
            try:
                it = croniter(cron_str, datetime.now())
                next_run = it.get_next(datetime).strftime("%a %H:%M")
                st.markdown(f"**Next Run**: {next_run}")
            except: pass
        
        # MaxMind License Check
        if check_licence_status():
            st.markdown("**MaxMind Key**: Active")
        else:
            st.markdown("**MaxMind Key**: Missing")


        st.divider()
        with st.expander("🛠️ Technical Support Download"):
            st.write("Click below to gather system diagnostics and raw appliance logs.")
            
            # 1. Action Button: Triggers the ZIP creation on the filesystem
            if st.button("Generate Support Archive (.zip)", use_container_width=True):
                with st.spinner("🔍 Compiling diagnostics and logs..."):
                    # Ensure we have the correct root path
                    root_dir = os.path.abspath(os.getcwd())
                    
                    # Pull SSH results from state if they exist
                    last_test = st.session_state.get('ssh_test_results')
                    
                    # Use the new function to create the actual ZIP
                    # This handles the JSON report + raw appliance.log
                    bundle_path = create_support_bundle(root_dir, ssh_test_log=last_test)
                    
                    if bundle_path and os.path.exists(bundle_path):
                        st.session_state['support_bundle_path'] = bundle_path
                        st.success("Archive generated successfully!")
                    else:
                        st.error("Failed to generate support bundle. Check system logs.")

            # 2. Download Button: Serves the physical ZIP file
            if 'support_bundle_path' in st.session_state:
                bundle_path = st.session_state['support_bundle_path']
                
                with open(bundle_path, "rb") as f:
                    st.download_button(
                        label="📥 Download ZIP Bundle",
                        data=f,
                        file_name=os.path.basename(bundle_path),
                        mime="application/zip",
                        use_container_width=True,
                        # Cleanup the zip from disk and state after download
                        on_click=lambda: [os.remove(bundle_path) if os.path.exists(bundle_path) else None, 
                                        st.session_state.pop('support_bundle_path', None)]
                    )

        # 4. Logout button & legal stuff
        authenticator.logout('Logout', 'sidebar', use_container_width=True)
        st.divider()
        st.caption(f"Version: {VERSION_NUMBER}", text_alignment="center")
        st.caption("© 2026 Loadbalancer.org All rights reserved.")
        st.caption("Licensed under Apache License 2.0")

    # --- SIDEBAR CONSTRUCTION - end ---

    # Load existing schedule
    if check_schedule_status(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, "r") as f:
                saved_cron = f.read().strip()
    else:
            saved_cron = "0 10 * * 3" # Default: Weekly on a Wednesday @ 10AM
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Settings", "Run History", "Scheduling", "Storage Management", "User Management"])
    
    with tab1:
        st.header("⚙️ Production Settings")
        
        # --- Section 1: MaxMind API Key ---
        st.subheader("1. MaxMind License Key")
        if check_licence_status():
            label = "Installed"
            status_color = "green"
            status_icon = ":material/check_circle:"
        else:
            label = "Not Installed"
            status_color = "red"
            status_icon = ":material/error:"
        
        st.write("MaxMind API key status:")
        st.badge(label, color=status_color, icon=status_icon)


        with st.expander("Update MaxMind License Key", expanded=False):
            new_key = st.text_input("Enter MaxMind API Key", type="password")

            if st.button("🔐 Verify & Save"):
                clean_key = new_key.strip()

                # Phase 1: Local Check (The 'Cheese' Filter)
                if not is_valid_format(clean_key):
                    logger.error("MaxMind Invalid Format: Please check your key for spaces or length errors.")
                    st.error("❌ Invalid Format: Please check your key for spaces or length errors.")
                
                else:
                    # Phase 2: Remote Check (The 'Fast' Ping)
                    with st.spinner("Checking key with MaxMind..."):
                        is_ok, msg = test_connection(clean_key)
                        
                        if is_ok:
                            encrypt_license(clean_key)
                            logger.info(f"MaxMind key successfully updated and encrypted by {st.session_state['username']}")
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")


        st.divider()

        # --- Section 2: Deployment Strategy Selector ---
        st.subheader("2. Deployment Strategy")
               
        # Load current settings safely
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r") as f:
                    current_settings = json.load(f)
            except Exception:
                current_settings = {"retention_limit": 4, "deployment_mode": "Remote Only"}
        else:
            current_settings = {"retention_limit": 4, "deployment_mode": "Remote Only"}

        # Strategy Selector
        selected_mode = st.radio(
            "How should the system handle the output?",
            options=["Local Only", "Remote Only", "Both"],
            index=["Local Only", "Remote Only", "Both"].index(current_settings.get("deployment_mode", "Remote Only")),
            horizontal=True,
            help="Local Only: Generate files but do not push. Remote Only: Pushes to servers. Both: Does both."
        )

        # Save Button for Strategy
        if st.button("💾 Save Deployment Strategy", width="content"):
            current_settings["deployment_mode"] = selected_mode
            with open(SETTINGS_PATH, "w") as f:
                json.dump(current_settings, f)
            logger.info(f"Deployment Strategy updated to {selected_mode}")
            st.success(f"Strategy updated to: **{selected_mode}**")
            st.rerun()

        st.divider()

        # --- Section 3: SSH Key Management ---
        st.subheader("3. SSH Security")

        # Check if a key already exists to display on load
        current_pub_key = get_public_key()

        if st.button("Generate New SSH Key Pair"):
            with st.spinner("Generating 4096-bit RSA keys..."):
                current_pub_key = generate_ssh_keys()
                logger.info("New key pair generated in /config")
                st.success("New key pair generated in /config")

        if current_pub_key:
            #st.info("Copy this Public Key to your remote servers' `~/.ssh/authorized_keys` file:")
            st.info("Copy this Public Key to your Target System", icon=":material/info:")
            st.info("`For Loadbalancer appliances: Local Configuration > SSH Keys > SSH Authentication > User Keys (authorized_keys)`", icon=":material/info:")
            st.code(current_pub_key, language="text", wrap_lines=True)

            # Add the download button here
            st.download_button(
                label="Download Public Key (.pub)",
                data=current_pub_key,
                file_name="public_key.pub",
                mime="text/plain",
                help="Click to download the public key"
            )
        else:
            st.warning("No SSH key found. Please generate one to enable remote deployment.")

        st.divider()

        # --- Section 4: Remote Target Servers ---
        st.subheader("4. Remote Deployment Targets")

        # Check if the API is installed 
        has_license = check_licence_status()
        
        if not has_license:
            st.warning("⚠️ Manual push is disabled until a MaxMind API Key is configured.", icon="🚫")

        # check if we are set to local only
        is_local_only = current_settings.get("deployment_mode") == "Local Only"

        if is_local_only:
            st.info("Disabled - you are running as Local Only - please go to the 'Storage Management' tab to download the latest GeoIP.dat file", icon=":material/info:")
        
        st.write("Define the servers where the `geoip.dat` file will be pushed.")

        # Load the current state from the file
        if 'server_data' not in st.session_state:
            st.session_state.server_data = load_servers()

        # Display the interactive editor
        edited_data = st.data_editor(
            st.session_state.server_data, 
            num_rows="dynamic", 
            width="stretch",
            disabled=is_local_only,
            column_config={
                "Host": st.column_config.TextColumn("IP or Hostname", help="The remote server address"),
                "Path": st.column_config.TextColumn("Path on Remote Target - must exist", help="The file path on the remote target to deploy the GeoIP.dat"),
                "User": st.column_config.TextColumn("SSH User", help="Username for SSH login"),
                "Command": st.column_config.TextColumn("Post-Deploy Command (Optional)", help="Example: systemctl restart httpd")
            }
        )

        # Save button logic
        if st.button("💾 Save Remote Targets", disabled=is_local_only):
            all_valid = True 
            for row in edited_data:
                is_ok, msg = validate_command(row.get("Command", ""))
                if not is_ok:
                    st.error(f"Error on {row['Host']}: {msg}")
                    all_valid = False
            
            if all_valid:                
                save_servers(edited_data)
                st.session_state.server_data = edited_data
                st.session_state.ssh_test_results = None    
                st.success(f"✅ Successfully saved {len(edited_data)} server(s)")
                logger.info(f"Successfully saved {len(edited_data)} servr(s)")
                st.toast("Configuration Updated", icon="💾")
                st.rerun()
            else:
                st.warning("⚠️ Changes were not saved due to security validation errors.")

        # Test button 
        if 'ssh_test_results' not in st.session_state:
            st.session_state.ssh_test_results = None

        if st.button("🔌 Test All Connections", disabled=is_local_only):
            results_log = []
            all_passed = True
            
            with st.status("Testing server reachability...", expanded=True) as status:
                servers = load_servers()
                for server in servers:
                    success, message = test_server_connection(server)
                    icon = "✅" if success else "❌"
                    results_log.append({"host": server['Host'], "msg": message, "success": success})
                    st.write(f"{icon} **{server['Host']}**: {message}")
                    if not success:
                        all_passed = False
                
                status.update(label="Tests Finished", state="complete" if all_passed else "error")
            
            # Save the results to state so they survive the next rerun
            st.session_state.ssh_test_results = {
                "log": results_log,
                "all_passed": all_passed,
                "timestamp": datetime.now().strftime("%H:%M:%S")
        }
            
        # --- SSH Identity Reset (Utility) ---
        if len(st.session_state.server_data) > 0 and not is_local_only:
            with st.expander("🛠️ SSH Identity Troubleshooting"):
                st.write("If a server has been rebuilt, click below to clear the stored SSH identity.")
                
                # Create a list of hosts for the dropdown
                host_list = [s['Host'] for s in st.session_state.server_data]
                selected_to_purge = st.selectbox("Select host to reset:", options=host_list)
                
                if st.button("🧹 Clear Host Identity"):
                    logger.info(f"Clearing host SSH: {selected_to_purge}")
                    # 1. Clear UI's own cache                    
                    remove_ssh_host_identity(selected_to_purge)
                    
                    # 2. Drop flag for the Worker
                    purge_request = {"target": selected_to_purge}
                    with open("data/purge_ssh.json", "w") as f:
                        json.dump(purge_request, f)
                    
                    st.success(f"Identity for {selected_to_purge} cleared from UI and Worker.")
                    st.toast("SSH Cache Cleared", icon="🧹")

        if st.session_state.ssh_test_results:
            res = st.session_state.ssh_test_results
            
            if res["all_passed"]:
                st.success(f"Last test at {res['timestamp']}: All servers online!")
            else:
                with st.expander(f"⚠️ Test Results ({res['timestamp']}) - Some Failures", expanded=True):
                    for entry in res["log"]:
                        icon = "✅" if entry["success"] else "❌"
                        st.write(f"{icon} **{entry['host']}**: {entry['msg']}")
                    
                    if st.button("Clear Results"):
                        st.session_state.ssh_test_results = None
                        st.rerun()

        st.write("---")
        st.subheader("Targeted GeoIP Push")

        # 1. Get the list of available folders from the worker's sync file
        if os.path.exists(LIST_PATH):
            with open(LIST_PATH, "r") as f:
                available_folders = json.load(f)
        else:
            available_folders = []

        if not available_folders:
            st.warning("No GeoIP folders found in storage. Run a task first.")
        else:
            col1, col2, col3 = st.columns([2, 2, 1])
            
            # Select which server
            target_server = col1.selectbox(
                "Select Target Server", 
                options=st.session_state.server_data,
                format_func=lambda x: f"{x['Host']} ({x['Path']})"
            )
            
            # Select which version of the data
            selected_folder = col2.selectbox("Select GeoIP Version", options=available_folders)

            # Trigger Button
            is_disabled = (not has_license) or is_local_only
            if col3.button("🚀 Push Now", width="stretch", disabled=is_disabled ):
                push_request = {
                    "server": target_server,
                    "folder": selected_folder,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Write the request file to the shared volume
                request_path = os.path.join("data", "push_request.json")
                with open(request_path, "w") as f:
                    json.dump(push_request, f)
                    
                st.success(f"Push request for **{selected_folder}** sent to Worker for **{target_server['Host']}**")
                st.toast("Worker notified!", icon="📤")
    

        st.divider()
            
         # --- Section 5: Storage setting retention ---
        st.subheader("5. Storage Settings")      

        # Load current setting
        current_limit = 4
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r") as f:
                settings = json.load(f)
                current_limit = settings.get("retention_limit", 4)

        new_limit = st.number_input(
            "Number of GeoIP files to keep", 
            min_value=1, 
            max_value=20, 
            value=current_limit,
            help="The worker will automatically delete the oldest folders when this limit is exceeded."
        )

        if st.button("💾 Save Storage Settings"):
            with open(SETTINGS_PATH, "w") as f:
                json.dump({"retention_limit": new_limit}, f)
            logger.info(f"Retention limit updated to {new_limit}")
            st.success(f"Retention limit updated to {new_limit}")

    with tab2:
        st.header("📜 Execution History")
        
        if os.path.exists("data/history.db"):
            conn = sqlite3.connect("data/history.db")
            # Pull the last 50 runs, newest first
            df = pd.read_sql_query("SELECT timestamp, task_type, status, details FROM task_history ORDER BY timestamp DESC LIMIT 50", conn)
            conn.close()

            if not df.empty:
                # Color coding the status for a production feel
                def color_status(val):
                    color = 'red' if val == 'Failed' else 'green' if val == 'Success' else 'orange'
                    return f'color: {color}; font-weight: bold'

                st.dataframe(df.style.map(color_status, subset=['status']), width="stretch")
            else:
                st.info("No history recorded yet. The worker will log tasks here once they run.")
        else:
            st.warning("History database not initialized. It will be created on the first task run.")

        if st.button("🔄 Refresh History", width="stretch"):
            st.rerun()


        if st.button("🗑️ Clear History", width="stretch"):
            clear_entire_database()
            st.toast("History Cleared", icon=":material/info:", duration="long")
            st.rerun()

    with tab3:
        st.header("🕒 Task Scheduling")

        # Check license status first
        has_license = check_licence_status()
        
        if not has_license:
            st.error("⚠️ **System Blocked:** You must install a MaxMind API Key in the 'Settings' tab before you can schedule or run tasks.")
        else:
            st.info("💡 Files deploy to configured path on all servers in your list.")

        if check_schedule_status(SCHEDULE_FILE):
            label = "Scheduled"
            status_color = "green"
            status_icon = ":material/check_circle:"
        else:
            label = "Not Scheduled"
            status_color = "red"
            status_icon = ":material/error:"

        st.write("Scheduled run status:")
        st.badge(label, color=status_color, icon=status_icon)

        # 2. Cron Input
        cron_input = st.text_input("Cron Expression", value=saved_cron)

        # 3. Human Readable Preview
        try:
            iter = croniter(cron_input, datetime.now())
            next_run = iter.get_next(datetime)
            logger.info(f"Next Run: {next_run.strftime('%A, %d %B %Y, %H:%M')}")
            st.success(f"📅 **Next Run:** {next_run.strftime('%A, %d %B %Y, %H:%M')}")
        except Exception:
            st.error("Invalid Cron Expression. Format: 'min hour day month day_of_week'")
        
        # 4. Action Buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Save & Update Worker", width="stretch", disabled=not has_license):
                with open(SCHEDULE_FILE, "w") as f:
                    f.write(cron_input)
                logger.info(f"Schedule saved! Restarting worker sequence...")
                st.toast("Schedule saved! Restarting worker sequence...", icon=":material/info:", duration="long")
                st.rerun()

        with col2:
            if st.button("🚀 Trigger Manual Run", width="stretch", disabled=not has_license):
                FLAG_FILE = "data/run_now.flag"
                with open(FLAG_FILE, "w") as f:
                    f.write(f"Triggered by UI at {datetime.now()}")
                st.toast("Manual run signal sent to worker!", icon=":material/info:", duration="long")
                logger.info("The worker has been notified. Check the History tab in a moment.")
                st.info("The worker has been notified. Check the History tab in a moment.")

        st.info("looking to update 1 Remote server? This can be done from the setting page in the SSH section.", icon=":material/info:")

    with tab4:
        st.subheader("GeoIP Storage Management")
        st.info("GeoIP folder present in the file storage")
        st.success("💾 GeoIP databases are safely backed up to persistent storage and will automatically restore if the system reboots.")
        st.caption("The files below represent currently active and deployed database versions.")

        # Use absolute paths to ensure we are looking in the shared data volume
        base_dir = os.path.abspath(os.getcwd())
        list_path = os.path.join(base_dir, "data", "legacy_list.json")
        delete_request_path = os.path.join(base_dir, "data", "delete_request.txt")
        download_req_path = os.path.join(base_dir, "data", "download_request.txt")
        transfer_zone = os.path.join(base_dir, "data", "transfer_zone")

        # Layout for the header and a refresh button
        col_head, col_ref = st.columns([4, 1])
        with col_ref:
            if st.button("🔄 Refresh List"):
                st.rerun()

        if os.path.exists(list_path):
            try:
                with open(list_path, "r") as f:
                    folders = json.load(f)

                if folders:
                    st.write(f"Found **{len(folders)}** dated GeoIP folders in storage:")
                    logger.info(f"Found {len(folders)} dated GeoIP folders in storage:")
                    
                    for folder in folders:
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2, 1, 1])
                            c1.write(f"📁 **{folder}**")
                            
                            staged_file = os.path.join(transfer_zone, f"GeoIP_{folder}.dat")
                            
                            if os.path.exists(staged_file):
                                with open(staged_file, "rb") as f:
                                    c2.download_button(
                                        label="📥 Download",
                                        data=f,
                                        file_name=f"GeoIP_{folder}.dat",
                                        mime="application/octet-stream",
                                        key=f"dl_{folder}"
                                    )
                            else:
                                if c2.button("Prepare", key=f"prep_{folder}"):
                                    with open(download_req_path, "w") as f:
                                        f.write(folder)
                                    st.toast("Worker is fetching file...", icon="⏳")

                            if c3.button("Delete", key=f"del_{folder}", type="secondary"):
                                with open(delete_request_path, "w") as f:
                                    f.write(folder)
                                st.toast("Delete request sent.")

                else:
                    st.write("Worker reported 0 legacy folders.")
            except Exception as e:
                st.error(f"Error reading legacy list: {e}")
        else:
            st.warning("Waiting for Worker to sync... (This can take up to 10 seconds)")
            st.caption(f"Searching for: {list_path}")

        # --- Transfer Zone Management ---
        if os.path.exists(transfer_zone) and os.listdir(transfer_zone):
            with st.expander("🧹 Manage Staged Downloads", expanded=False):
                st.write("These files are currently taking up space in the shared data folder.")
                if st.button("Clear All Staged Downloads", width="content"):
                    shutil.rmtree(transfer_zone)
                    os.makedirs(transfer_zone)
                    st.rerun()

    with tab5:
        st.header("👤 User Management")
        
        # --- Section 1: Update Profile ---
        with st.expander("📝 Update My Details"):
            try:
                # v0.4.2 signature uses 'username' and 'location'
                if authenticator.update_user_details(st.session_state.get('username'), location='main'):
                    with open(auth_file, 'w') as file:
                        yaml.dump(config, file, default_flow_style=False)
                    st.success('Entries updated successfully')
            except Exception as e:
                st.error(f"Update error: {e}")

        # --- Section 2: Change Password ---
        with st.expander("🔐 Change Password"):
            try:
                if authenticator.reset_password(username=st.session_state.get('username'), location='main'):
                    with open(auth_file, 'w') as file:
                        yaml.dump(config, file, default_flow_style=False)
                    st.success('Password modified successfully')
            except Exception as e:
                st.error(f"Reset error: {e}")

        # --- Section 3: Register New User ---
        # Note: You might want to wrap this in an 'if username == "admin"' check 
        # so only the superuser can add new people.
        #with st.expander("➕ Register New Operator"):
        #    st.info("Authorized emails must be listed in the 'pre-authorized' section of auth.yaml.")
        #    try:
                # v0.4.2 signature: register_user(location='main', pre_authorized=config['preauthorized']['emails'])
                # Note the key 'preauthorized' matches your YAML structure provided earlier
        #        email_reg, user_reg, name_reg = authenticator.register_user(
        #            location='main', 
        #            pre_authorized=config.get('preauthorized', {}).get('emails', [])
        #        )
        #        if email_reg:
        #            with open(auth_file, 'w') as file:
        #                yaml.dump(config, file, default_flow_style=False)
        #            st.success(f'User {user_reg} registered successfully')
        #    except Exception as e:
        #        st.error(f"Registration error: {e}")

    st.divider()

elif st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password')