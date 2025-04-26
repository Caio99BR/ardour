import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import tarfile
import zipfile
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import hashlib
import threading

# Configuration
BASE_URL = "https://nightly.ardour.org/list.php#build_deps"
PACKAGE_MAP_FILE = 'msys_package_map.json'
DOWNLOAD_DIR = "downloads"
EXTRACT_DIR = "extracted"
INSTALL_DIR = "/usr/local"  # Change this if you want to install elsewhere
INSTALL = False  # Set to True to run 'make install'
MAX_THREADS = 4  # Adjust as needed (now supporting multiple threads)
GENERATE_PACKAGE_MAP = False  # Set to True to generate the msys_package_map.json file
USE_REMOTE_PACKAGE_MAP = False  # Set to True to use the remote package map (proceed with caution)

# Load package map from JSON file
def load_msys2_package_map(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {file_path} not found. Proceeding without MSYS2 package map.")
        return {}

# Save site hash to JSON file
def save_site_hash_to_json(hash_value, file_path):
    package_map = load_msys2_package_map(file_path)
    package_map['site_hash'] = hash_value
    with open(file_path, 'w') as f:
        json.dump(package_map, f, indent=4)
    print(f"Site hash {hash_value} saved to {file_path}")

# Compare current hash to saved one
def check_site_for_changes():
    response = requests.get(BASE_URL)
    response.raise_for_status()
    current_hash = hashlib.sha256(response.text.encode('utf-8')).hexdigest()
    saved_hash = load_msys2_package_map(PACKAGE_MAP_FILE).get('site_hash')
    if saved_hash != current_hash:
        if GENERATE_PACKAGE_MAP:
            save_site_hash_to_json(current_hash, PACKAGE_MAP_FILE)
        return True
    return False

# Generate updated package map from Ardour's site
def generate_msys2_package_map():
    try:
        response = requests.get(BASE_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        deps_section = soup.find("ul", class_="multicolumn")
        if not deps_section:
            raise ValueError("Could not find the list of dependencies.")

        package_map = {}

        for li in deps_section.find_all("li"):
            link = li.find("a")
            if not link or not link.get("href"):
                continue
            url = link["href"]
            filename = os.path.basename(url)
            base = filename.split('-')[0]
            msys2_package = f"mingw-w64-x86_64-{base}"
            description = link.text.strip()
            special_flag = "special" if "ardour.org" in url else "normal"

            package_map[base] = {
                "url": url,
                "msys2_package": msys2_package,
                "special_flag": special_flag,
                "description": description
            }

        current_hash = hashlib.sha256(response.text.encode('utf-8')).hexdigest()
        package_map['site_hash'] = current_hash
        return package_map

    except Exception as e:
        print(f"Error generating MSYS2 package map: {e}")
        return {}

# Check for site changes and optionally update the package map
site_changed = check_site_for_changes()
if site_changed:
    print("The Ardour dependency list has changed.")
    if GENERATE_PACKAGE_MAP:
        print("Generating updated package map...")
        MSYS2_PACKAGE_MAP = generate_msys2_package_map()
        with open(PACKAGE_MAP_FILE, 'w') as f:
            json.dump(MSYS2_PACKAGE_MAP, f, indent=4)
        print(f"Package map updated and saved to {PACKAGE_MAP_FILE}")
    else:
        print("Changes detected but GENERATE_PACKAGE_MAP is False. Package map not updated.")
else:
    print("No changes detected on the Ardour dependency list.")

# Determine which package map to use
if not os.path.exists(PACKAGE_MAP_FILE):
    print(f"Local package map not found! Using remote package map as fallback...")
    MSYS2_PACKAGE_MAP = generate_msys2_package_map()
elif USE_REMOTE_PACKAGE_MAP:
    print("Using remote package map (proceed with caution)...")
    MSYS2_PACKAGE_MAP = generate_msys2_package_map()
else:
    print("Using local package map from JSON file...")
    MSYS2_PACKAGE_MAP = load_msys2_package_map(PACKAGE_MAP_FILE)

# Ensure directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

# Main process: download, extract, and optionally install
total = sum(1 for base in MSYS2_PACKAGE_MAP if isinstance(MSYS2_PACKAGE_MAP[base], dict))
current_lock = threading.Lock()
current = [1]  # Using a list to allow mutation across threads
current[0] = 1
downloaded_files = []

with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    futures = []

    def task(base, info):
        with current_lock:
            current_value = current[0]
            current[0] += 1  # Increment within the lock to ensure thread safety

        url = info.get("url")
        filename = os.path.basename(url)
        msys2_package = info["msys2_package"]
        special_flag = info["special_flag"]

        if not url:
            print(f"[{current_value}/{total}] {msys2_package} No URL found for package. Skipping.")
            return

        if special_flag == "none":
            print(f"[{current_value}/{total}] {msys2_package} Skipping package (flagged as 'none').")
            return

        # Check if the package is already installed or install it if not
        if special_flag != "special":
            try:
                result = subprocess.run(["pacman", "-Q", msys2_package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if result.returncode == 0:
                    print(f"[{current_value}/{total}] {msys2_package} is already installed. Skipping.")
                    return
                result = subprocess.run(["pacman", "-S", "--noconfirm", msys2_package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode == 0:
                    print(f"[{current_value}/{total}] {msys2_package} Successfully installed using pacman.")
                    return
            except Exception as e:
                print(f"[{current_value}/{total}] {msys2_package} Error checking package: {e}. Proceeding with download and extraction.")

        try:
            # Check if the file already exists
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.exists(file_path):
                print(f"[{current_value}/{total}] {msys2_package} {filename} already downloaded. Skipping.")
                return

            # Download the file
            print(f"[{current_value}/{total}] {msys2_package} Downloading {filename}...")
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    total_size = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            print(f"\r[{current_value}/{total}] {msys2_package} Downloading {filename}: {downloaded/total_size*100:.2f}% complete", end="")
            print(f"\n[{current_value}/{total}] {msys2_package} Downloaded {filename} ({total_size/1024/1024:.2f} MB)")
        except Exception as e:
            print(f"[{current_value}/{total}] {msys2_package} Failed {filename}: {e}")
            return

        try:
            # Extract the file
            extract_path = os.path.join(EXTRACT_DIR, os.path.splitext(filename)[0])
            if not os.path.exists(extract_path):
                print(f"[{current_value}/{total}] {msys2_package} Extracting {filename}...")
                if filename.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")):
                    with tarfile.open(file_path, "r:*") as tar:
                        tar.extractall(path=extract_path)
                elif filename.endswith(".zip"):
                    with zipfile.ZipFile(file_path, "r") as zip_ref:
                        zip_ref.extractall(path=extract_path)
                else:
                    print(f"[{current_value}/{total}] {msys2_package} Unknown file format: {filename}")
                    return
            else:
                print(f"[{current_value}/{total}] {msys2_package} {filename} already extracted. Skipping extraction.")

            downloaded_files.append(filename)
        except Exception as e:
            print(f"[{current_value}/{total}] {msys2_package} Failed {filename}: {e}")
            return

    # Submit the tasks to the thread pool
    for base, info in MSYS2_PACKAGE_MAP.items():
        if isinstance(info, dict):
            futures.append(executor.submit(task, base, info))

    try:
        for future in as_completed(futures):
            future.result()

        if INSTALL:
            for filename in downloaded_files:
                extract_path = os.path.join(EXTRACT_DIR, os.path.splitext(filename)[0])
                print(f"Installing {filename}...")
                original_dir = os.getcwd()
                inner_dir = os.path.join(extract_path, filename.split('-')[0] + '-' + filename.split('-')[1])
                os.chdir(inner_dir if os.path.exists(inner_dir) else extract_path)
                os.system(f"./configure --prefix={INSTALL_DIR}")
                os.system("make")
                os.system("make install")
                os.chdir(original_dir)

    except Exception as e:
        print(f"An error occurred during execution: {e}")
