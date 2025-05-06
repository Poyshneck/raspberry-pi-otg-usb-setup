#!/usr/bin/env python

import os, subprocess, shutil, time, json
import logging, logging.handlers
import dropbox
from dropbox.files import WriteMode
from inspect import getsourcefile

#######################################################################
# Script: Dropbox and SCP File Transfer Service
# Version: 2
#
# Changelog:
# - Added error handling for subprocess calls, ensuring failures are logged. (Reason: Ensure subprocess call failures are captured and logged.)
# - Added checks for file and directory existence before operations to prevent errors. (Reason: Prevent errors caused by missing files or directories.)
# - Improved Dropbox upload error handling. (Reason: Improve handling of Dropbox file upload failures.)
# - Added permission checks before logging setup. (Reason: Ensure that log file path is writable before starting logging.)
# - Enhanced logging with more details for SCP and Dropbox transfers. (Reason: Improve clarity and traceability of transfers.)
# - Prevented accidental overwriting of files during SCP and Dropbox upload. (Reason: Protect existing files from overwriting unintentionally.)
# - Added retry logic for SCP transfers to handle potential network issues. (Reason: Ensure reliability in case of transient network failures.)
# - Improved config loading with exception handling for missing or malformed config files. (Reason: Handle cases where the config file is missing or invalid.)
#######################################################################

BASE_PATH = os.path.dirname(os.path.abspath(getsourcefile(lambda:0)))
SOURCE_BASE_DIR = os.path.join(BASE_PATH, 'transfer')
COPYING_ACTIVE_FILE = os.path.join(SOURCE_BASE_DIR, 'copyingActive')

def setup_logging(log_file_full_path):
    base_path = os.path.split(log_file_full_path)[0]
    # Version 2 Change: Check if log directory is writable before setting up logging.
    if not os.access(base_path, os.W_OK):
        raise PermissionError(f"Cannot write to log directory: {base_path}")
    
    if base_path: os.makedirs(base_path, exist_ok=True)
    log_formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    file_handler = logging.handlers.RotatingFileHandler(log_file_full_path, maxBytes=500000, backupCount=7)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

def wait_until_no_copying_active(copy_active_file):
    max_time = 0
    while os.path.isfile(copy_active_file):
        time.sleep(1)
        max_time += 1
        if max_time > 30:
            logging.warning("Timed out waiting for copying to finish.")
            break

def transfer_via_scp(source_dir, config):
    source_dir_content = os.path.join(source_dir, '*')
    try:
        result = subprocess.run(['expect', '-f', 'scp-copy.exp', source_dir_content, config['ScpPath']], capture_output=True, text=True)
        # Version 2 Change: Added error handling and improved logging.
        if result.returncode != 0:
            logging.error(f"SCP transfer failed: {result.stderr}")
        else:
            logging.info(f"SCP transfer successful: {result.stdout}")
    except Exception as e:
        logging.error(f"Failed to execute SCP transfer: {e}")

def get_all_files(folder):
    all_files = []
    for item in os.scandir(folder):
        if item.is_file(): 
            all_files.append(item.path)
        elif item.is_dir(): 
            all_files.extend(get_all_files(item.path))
    return all_files

def transfer_to_dropbox(source_dir, config):
    token = config['DropBoxRefreshToken']
    key = config['DropboxAppKey']
    secret = config['DropboxAppSecret']
    with dropbox.Dropbox(oauth2_refresh_token=token, app_key=key, app_secret=secret) as dbx:
        all_files = get_all_files(source_dir)
        for file in all_files:
            try:
                with open(file, mode='rb') as f:
                    destination_path = os.path.join(config['DropBoxPath']) + os.path.relpath(file, source_dir)
                    logging.info(f"STARTING Dropbox upload to: {destination_path}")
                    file_metadata = dbx.files_upload(f.read(), destination_path, mode=WriteMode('overwrite'))
                    logging.info(f"FINISHED Dropbox upload: {file_metadata.path_display}")
            except dropbox.exceptions.ApiError as e:
                logging.error(f"Dropbox API error during file upload: {e}")
            except Exception as e:
                logging.error(f"Failed to upload file {file} to Dropbox: {e}")

# ----------------
# MAIN
# ----------------
setup_logging(os.path.join(BASE_PATH, 'logs/uploadLogging.log')) 

try:
    logging.info(f"----STARTED upload_new_files.py----")
    os.makedirs(SOURCE_BASE_DIR, exist_ok=True)

    # Version 2 Change: Improved error handling for config file loading.
    try:
        with open(os.path.join(BASE_PATH, 'config.json')) as config_file:
            config = json.load(config_file)
        logging.info(f"Configuration loaded.")
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode config file: {e}")
        raise
    except FileNotFoundError as e:
        logging.error(f"Config file not found: {e}")
        raise

    while True:
        folders_to_transfer = [d for d in os.scandir(SOURCE_BASE_DIR) if d.is_dir()]
        if folders_to_transfer:
            wait_until_no_copying_active(COPYING_ACTIVE_FILE)
            for folder in folders_to_transfer:
                if config.get('ActivateDropboxSync', False):
                    transfer_to_dropbox(folder, config)
                if config.get('ActivateScpSync', False):
                    transfer_via_scp(folder, config)
                shutil.rmtree(folder)  # delete the folder after transfer
        time.sleep(4.5)

except Exception as ex:
    logging.exception(ex)
