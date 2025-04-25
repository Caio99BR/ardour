import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import tarfile
import zipfile
import shutil

# Configuration
BASE_URL = "https://nightly.ardour.org/list.php#build_deps"
DOWNLOAD_DIR = "downloads"
EXTRACT_DIR = "extracted"
INSTALL_DIR = "/usr/local"  # Change this if you want to install elsewhere
INSTALL = False  # Set to True to run 'make install'

# Ensure directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

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
