import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import tarfile
import zipfile
import shutil
import subprocess

# Configuration
BASE_URL = "https://nightly.ardour.org/list.php#build_deps"
DOWNLOAD_DIR = "downloads"
EXTRACT_DIR = "extracted"
INSTALL_DIR = "/usr/local"  # Change this if you want to install elsewhere
INSTALL = False  # Set to True to run 'make install'

# Ensure directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

# Function to check if a package is installed and the version is sufficient
def check_installed_version(package_name, required_version):
    try:
        result = subprocess.run([package_name, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            installed_version = result.stdout.decode().strip().split()[1]  # Assuming version is the second word
            # Compare versions (this is a simple comparison, needs more advanced handling for complex versions)
            if installed_version >= required_version:
                print(f"{package_name} version {installed_version} is sufficient.")
                return True
            else:
                print(f"{package_name} version {installed_version} is lower than required {required_version}.")
                return False
        else:
            print(f"{package_name} is not installed.")
            return False
    except Exception as e:
        print(f"Error checking version of {package_name}: {e}")
        return False

# Fetch the dependency list page
response = requests.get(BASE_URL)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

# Find the list of dependencies
deps_section = soup.find("ul", class_="multicolumn")
if not deps_section:
    raise ValueError("Could not find the dependencies list on the page.")

# Process each dependency
for li in deps_section.find_all("li"):
    link = li.find("a")
    if not link or not link.get("href"):
        continue
    url = link["href"]
    filename = os.path.basename(url)
    package_name, required_version = filename.split('-')[:2]  # Assume filename format: <name>-<version>
    required_version = required_version.replace(".tar", "").replace(".gz", "").replace(".bz2", "").replace(".xz", "")

    # Check if the package version is installed and sufficient
    if check_installed_version(package_name, required_version):
        print(f"{package_name} is already installed with the required version. Skipping download.")
        continue

    # If package is not installed or the version is outdated, download and extract
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    extract_path = os.path.join(EXTRACT_DIR, os.path.splitext(filename)[0])

    # Check if file already exists
    if not os.path.exists(filepath):
        print(f"Downloading {filename}...")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(filepath, "wb") as f:
                shutil.copyfileobj(r.raw, f)
    else:
        print(f"{filename} already exists. Skipping download.")

    # Check if already extracted
    if not os.path.exists(extract_path):
        print(f"Extracting {filename}...")
        try:
            if filename.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")):
                with tarfile.open(filepath, "r:*") as tar:
                    tar.extractall(path=extract_path)
            elif filename.endswith(".zip"):
                with zipfile.ZipFile(filepath, "r") as zip_ref:
                    zip_ref.extractall(path=extract_path)
            else:
                print(f"Unknown archive format: {filename}. Skipping extraction.")
                continue
        except Exception as e:
            print(f"Failed to extract {filename}: {e}")
            continue
    else:
        print(f"{filename} already extracted. Skipping extraction.")

    # Optional installation
    if INSTALL:
        print(f"Installing {filename}...")
        # This assumes a standard './configure && make && make install' build process
        # You may need to adjust this for specific dependencies
        os.chdir(extract_path)
        os.system("./configure --prefix=" + INSTALL_DIR)
        os.system("make")
        os.system("make install")
        os.chdir("../../")  # Return to the original directory
