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

# Configuration
BASE_URL = "https://nightly.ardour.org/list.php#build_deps"
PACKAGE_MAP_FILE = 'msys_package_map.json'
DOWNLOAD_DIR = "downloads"
EXTRACT_DIR = "extracted"
INSTALL_DIR = "/usr/local"  # Change this if you want to install elsewhere
INSTALL = False  # Set to True to run 'make install'
MAX_THREADS = 4  # Adjust as needed
GENERATE_PACKAGE_MAP = False  # Set to True to generate the msys_package_map.json file
USE_REMOTE_PACKAGE_MAP = False  # Set to True to use the remote package map (proceed with caution)
CANCEL_FLAG = False

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

# Check if a MSYS2 package is installed
def check_msys2_package_installed(package_name):
    try:
        result = subprocess.run(["pacman", "-Q", package_name],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking package {package_name}: {e}")
        return False

# Try to install a MSYS2 package
def try_install_msys2_package(package_name):
    try:
        print(f"Attempting to install {package_name} using pacman...")
        result = subprocess.run(["pacman", "-S", "--noconfirm", package_name],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print(f"Successfully installed {package_name} using pacman.")
            return True
        else:
            print(f"Failed to install {package_name} using pacman.")
            return False
    except Exception as e:
        print(f"Error installing {package_name}: {e}")
        return False

# Allow cancellation of threaded tasks
def cancel_execution():
    global CANCEL_FLAG
    CANCEL_FLAG = True

# Get ETag (hash) of a remote file
def get_remote_file_hash(url):
    try:
        response = requests.head(url)
        response.raise_for_status()
        return response.headers.get("ETag")
    except requests.RequestException as e:
        print(f"Error getting file hash from {url}: {e}")
        return None

# Calculate SHA-256 hash of a local file
def get_local_file_hash(file_path):
    if not os.path.exists(file_path):
        return None
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

# Download and extract dependency if needed
def download_and_extract(dep, index=None, total=None):
    global CANCEL_FLAG

    url, filename, force_download = dep
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    extract_path = os.path.join(EXTRACT_DIR, os.path.splitext(filename)[0])

    if CANCEL_FLAG:
        print("Cancellation requested. Stopping download...")
        return

    try:
        remote_hash = get_remote_file_hash(url)
        local_hash = get_local_file_hash(file_path)

        if (
            os.path.exists(file_path)
            and os.path.exists(extract_path)
            and remote_hash
            and local_hash
            and remote_hash == local_hash
        ):
            print(f"✓ [{index}/{total}] {filename} already downloaded and extracted (hash match). Skipping.")
            return

        if force_download or not os.path.exists(file_path) or remote_hash != local_hash:
            print(f"[{index}/{total}] Downloading {filename}...")
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    total_size = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            print(f"\rDownloading {filename}: {downloaded/total_size*100:.2f}% complete", end="")
            print(f"\n✓ Downloaded {filename} ({total_size/1024/1024:.2f} MB)")

        if not os.path.exists(extract_path):
            print(f"[{index}/{total}] Extracting {filename}...")
            if filename.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")):
                with tarfile.open(file_path, "r:*") as tar:
                    tar.extractall(path=extract_path)
            elif filename.endswith(".zip"):
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(path=extract_path)
            else:
                print(f"Unknown file format: {filename}")
        else:
            print(f"{filename} already extracted. Skipping extraction.")
    except Exception as e:
        print(f"✗ [{index}/{total}] Failed {filename}: {e}")

# Scrape list of dependencies from Ardour website
response = requests.get(BASE_URL)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")
deps_section = soup.find("ul", class_="multicolumn")
if not deps_section:
    raise ValueError("Could not find the list of dependencies.")

download_list = []

# Prepare list of packages to download
for li in deps_section.find_all("li"):
    link = li.find("a")
    if not link or not link.get("href"):
        continue
    url = link["href"]
    filename = os.path.basename(url)
    base = filename.split('-')[0]

    package_info = MSYS2_PACKAGE_MAP.get(base)

    if package_info:
        msys2_package = package_info["msys2_package"]
        special_flag = package_info["special_flag"]
        description = package_info["description"]

        if special_flag == "none":
            print(f"Skipping package {base} (flagged as 'none').")
            continue

        if "ardour.org" not in url:
            if check_msys2_package_installed(msys2_package):
                print(f"{msys2_package} is already installed. Skipping.")
                continue
            elif try_install_msys2_package(msys2_package):
                print(f"Required package '{msys2_package}' installed successfully.")
                continue
    else:
        print(f"No MSYS2 package mapping found for {base}. Proceeding with download.")

    force_download = "ardour.org" in url
    download_list.append((url, filename, force_download))

# Start threaded downloads and extraction
with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    total = len(download_list)
    futures = {executor.submit(download_and_extract, dep, i, total): i for i, dep in enumerate(download_list, 1)}
    try:
        for future in as_completed(futures):
            future.result()
    except KeyboardInterrupt:
        print("Process interrupted. Cancelling...")
        cancel_execution()

# Optionally build and install from source
if INSTALL:
    for _, filename in download_list:
        extract_path = os.path.join(EXTRACT_DIR, os.path.splitext(filename)[0])
        print(f"Installing {filename}...")
        original_dir = os.getcwd()
        inner_dir = os.path.join(extract_path, filename.split('-')[0] + '-' + filename.split('-')[1])
        os.chdir(inner_dir if os.path.exists(inner_dir) else extract_path)
        os.system(f"./configure --prefix={INSTALL_DIR}")
        os.system("make")
        os.system("make install")
        os.chdir(original_dir)
