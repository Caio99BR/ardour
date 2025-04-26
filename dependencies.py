import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import tarfile
import zipfile
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import threading
import re

# Configuration
BASE_URL = "https://nightly.ardour.org/list.php#build_deps"
PACKAGE_MAP_FILE = 'msys_package_map.json'
DOWNLOAD_DIR = "downloads"
EXTRACT_DIR = "extracted"
INSTALL_DIR = "/usr/local"  # Change this if you want to install elsewhere
INSTALL = True  # Set to True to run 'make install'
MAX_THREADS = 4  # Adjust as needed (now supporting multiple threads)
GENERATE_PACKAGE_MAP = False  # Set to True to generate the msys_package_map.json file
USE_REMOTE_PACKAGE_MAP = False  # Set to True to use the remote package map (proceed with caution)
PRINT_SKIP = False

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

def task(base, info):
    with current_lock:
        installed = 0
        current_value = current[0]
        current[0] += 1  # Increment within the lock to ensure thread safety

    url = info.get("url")
    filename = os.path.basename(url)
    msys2_package = info["msys2_package"]
    special_flag = info["special_flag"]

    if not url:
        print(f"[{current_value}/{total}] {msys2_package} URL found, skipping...")
        return

    if special_flag == "none" or special_flag == "special":
        if PRINT_SKIP:
            print(f"[{current_value}/{total}] {msys2_package} flagged as '{special_flag}', skipping...")
        return

    # Check if the package is already installed or install it if not
    result = subprocess.run(["pacman", "-Q", msys2_package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode == 0:
        if PRINT_SKIP:
            print(f"[{current_value}/{total}] {msys2_package} is already installed. Skipping.")
        installed = 1
    else:
        result = subprocess.run(["pacman", "-S", "--noconfirm", msys2_package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            if PRINT_SKIP:
                print(f"[{current_value}/{total}] {msys2_package} successfully installed using pacman.")
            installed = 1

    if installed == 0:
        try:
            # Check if the file already exists
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.exists(file_path):
                print(f"[{current_value}/{total}] {msys2_package} {filename} already downloaded, skipping...")
            else:
                # Download the file
                print(f"[{current_value}/{total}] {msys2_package} Downloading {filename}...")
                with requests.get(url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(file_path, "wb") as f:
                        total_size = int(r.headers.get('content-length', 0))
                        downloaded = 0
                        if total_size == 0:  # Handle unknown file sizes
                            print(f"[{current_value}/{total}] {msys2_package} Downloading {filename}: Unknown size, downloading...")
                        for chunk in r.iter_content(chunk_size=1024):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                # Avoid division by zero by checking if total_size > 0
                                if total_size > 0:
                                    print(f"\r[{current_value}/{total}] {msys2_package} Downloading {filename}: {downloaded / total_size * 100:.2f}% complete", end="")
                        print(f"\n[{current_value}/{total}] {msys2_package} Downloaded {filename} ({total_size / 1024 / 1024:.2f} MB)")
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
                        for member in tar.getmembers():
                            sanitized_name = re.sub(r'[:]', '_', member.name)
                            member.name = sanitized_name
                        tar.extractall(path=extract_path)
                elif filename.endswith(".zip"):
                    with zipfile.ZipFile(file_path, "r") as zip_ref:
                        zip_ref.extractall(path=extract_path)
                else:
                    print(f"[{current_value}/{total}] {msys2_package} Unknown file format: {filename}")
                    return
            else:
                print(f"[{current_value}/{total}] {msys2_package} {filename} already extracted, skipping...")
        except Exception as e:
            print(f"[{current_value}/{total}] {msys2_package} Failed {filename}: {e}")
            return

        # Add to the list only after extraction is done
        with current_lock:
            downloaded_files.append(extract_path)

# Submit the tasks to the thread pool
with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    futures = []
    for base, info in MSYS2_PACKAGE_MAP.items():
        if isinstance(info, dict):
            futures.append(executor.submit(task, base, info))
    for future in futures:
        future.result()

if INSTALL:
    for extract_path in downloaded_files:
        original_dir = os.getcwd()
        subdirs = [f for f in os.listdir(extract_path) if os.path.isdir(os.path.join(extract_path, f))]
        if len(subdirs) == 1:
            build_dir = os.path.join(extract_path, subdirs[0])
        else:
            build_dir = extract_path
        print(f"Installing from {build_dir}...")
        os.chdir(build_dir)
        try:
            if os.system("bash ./configure --prefix=" + INSTALL_DIR) != 0:
                raise RuntimeError("Error during ./configure")

            if os.system("bash make") != 0:
                raise RuntimeError("Error during make")

            if os.system("bash make install") != 0:
                raise RuntimeError("Error during make install")

        except subprocess.CalledProcessError as e:
            print("Error during the build process:")
            print("Failed command:", e.cmd)
            print("Return code:", e.returncode)
            sys.exit(1)
        finally:
            os.chdir(original_dir)
