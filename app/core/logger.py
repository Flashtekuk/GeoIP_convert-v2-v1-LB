import logging
import logging.config
import json
import pathlib
import os

CONFIG_PATH = pathlib.Path("config/logger_config.json")
LOG_FILE = "data/appliance.log"

def setup_logging():
    """
    Standard logging setup for the Worker (non-Streamlit).
    """
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f_in:
            config = json.load(f_in)
        
        # Ensure the log directory exists
        os.makedirs("data", exist_ok=True)
        
        logging.config.dictConfig(config)
    else:
        # Fallback if config is missing
        logging.basicConfig(level=logging.INFO)
        logging.warning(f"Log config not found at {CONFIG_PATH}, using basicConfig.")

# --- Streamlit Specific Logic ---
try:
    import streamlit as st
    
    @st.cache_resource
    def get_ui_logger():
        """
        Initializes logging once and persists it across Streamlit reruns.
        """
        setup_logging()
        return logging.getLogger("UI")
except ImportError:
    # If we are in the Worker container, Streamlit won't be installed
    pass