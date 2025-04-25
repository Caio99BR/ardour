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

# Mapping dependency base names to MSYS2 package names
MSYS2_PACKAGE_MAP = {
    "aubio": "mingw-w64-x86_64-aubio",
    "autoconf": "mingw-w64-x86_64-autoconf",
    "automake": "mingw-w64-x86_64-automake",
    "bison": "mingw-w64-x86_64-bison",
    "boost": "mingw-w64-x86_64-boost",
    "cairo": "mingw-w64-x86_64-cairo",
    "cairomm": "mingw-w64-x86_64-cairomm",
    "cmake": "mingw-w64-x86_64-cmake",
    "cppunit": "mingw-w64-x86_64-cppunit",
    "curl": "mingw-w64-x86_64-curl",
    "expat": "mingw-w64-x86_64-expat",
    "fftw": "mingw-w64-x86_64-fftw",
    "flac": "mingw-w64-x86_64-flac",
    "flex": "mingw-w64-x86_64-flex",
    "fontconfig": "mingw-w64-x86_64-fontconfig",
    "freetype": "mingw-w64-x86_64-freetype",
    "fribidi": "mingw-w64-x86_64-fribidi",
    "gettext": "mingw-w64-x86_64-gettext",
    "glib": "mingw-w64-x86_64-glib2",
    "glibmm": "mingw-w64-x86_64-glibmm",
    "gnome-common": "mingw-w64-x86_64-gnome-common",
    "gnome-doc-utils": "mingw-w64-x86_64-gnome-doc-utils",
    "gobject-introspection": "mingw-w64-x86_64-gobject-introspection",
    "harfbuzz": "mingw-w64-x86_64-harfbuzz",
    "intltool": "mingw-w64-x86_64-intltool",
    "itstool": "mingw-w64-x86_64-itstool",
    "jpegsrc": "mingw-w64-x86_64-jpeg",
    "libarchive": "mingw-w64-x86_64-libarchive",
    "libffi": "mingw-w64-x86_64-libffi",
    "libiconv": "mingw-w64-x86_64-libiconv",
    "liblo": "mingw-w64-x86_64-liblo",
    "libogg": "mingw-w64-x86_64-libogg",
    "libpng": "mingw-w64-x86_64-libpng",
    "libsamplerate": "mingw-w64-x86_64-libsamplerate",
    "libsigc++": "mingw-w64-x86_64-libsigc++",
    "libsndfile": "mingw-w64-x86_64-libsndfile",
    "libtool": "mingw-w64-x86_64-libtool",
    "libusb": "mingw-w64-x86_64-libusb",
    "libvorbis": "mingw-w64-x86_64-libvorbis",
    "libwebsockets": "mingw-w64-x86_64-libwebsockets",
    "libxml2": "mingw-w64-x86_64-libxml2",
    "libxslt": "mingw-w64-x86_64-libxslt",
    "lilv": "mingw-w64-x86_64-lilv",
    "lv2": "mingw-w64-x86_64-lv2",
    "libgnurx": "mingw-w64-x86_64-libgnurx",
    "m4": "mingw-w64-x86_64-m4",
    "make": "mingw-w64-x86_64-make",
    "nss": "mingw-w64-x86_64-nss",
    "nss-pem": "mingw-w64-x86_64-nss-pem",
    "opus": "mingw-w64-x86_64-opus",
    "pango": "mingw-w64-x86_64-pango",
    "pangomm": "mingw-w64-x86_64-pangomm",
    "pcre": "mingw-w64-x86_64-pcre",
    "pixman": "mingw-w64-x86_64-pixman",
    "pkg-config": "mingw-w64-x86_64-pkg-config",
    "portaudio": "mingw-w64-x86_64-portaudio",
    "raptor2": "mingw-w64-x86_64-raptor2",
    "rasqal": "mingw-w64-x86_64-rasqal",
    "rdflib": "mingw-w64-x86_64-rdflib",
    "readline": "mingw-w64-x86_64-readline",
    "redland": "mingw-w64-x86_64-redland",
    "rubberband": "mingw-w64-x86_64-rubberband",
    "serd": "mingw-w64-x86_64-serd",
    "sord": "mingw-w64-x86_64-sord",
    "sratom": "mingw-w64-x86_64-sratom",
    "taglib": "mingw-w64-x86_64-taglib",
    "tar": "mingw-w64-x86_64-tar",
    "termcap": "mingw-w64-x86_64-termcap",
    "tiff": "mingw-w64-x86_64-tiff",
    "util-linux": "mingw-w64-x86_64-util-linux",
    "uuid": "mingw-w64-x86_64-uuid",
    "vamp-plugin-sdk": "mingw-w64-x86_64-vamp-plugin-sdk",
    "xz": "mingw-w64-x86_64-xz",
    "zlib": "mingw-w64-x86_64-zlib"
}

# Ensure directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

# Function to check if an MSYS2 package is installed
def check_msys2_package_installed(package_name):
    try:
        result = subprocess.run(["pacman", "-Q", package_name],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking package {package_name}: {e}")
        return False

# Function to try installing the package with pacman
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

# Fetch the dependency list page
response = requests.get(BASE_URL)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

# Find the list of dependencies
deps_section = soup.find("ul", class_="multicolumn")
if not deps_section:
    raise ValueError("Could not find the list of dependencies.")

# Process each dependency
for li in deps_section.find_all("li"):
    link = li.find("a")
    if not link or not link.get("href"):
        continue
    url = link["href"]

    # Handle redirect host
    #if "ftpmirror.gnu.org" in url:
    #    url = url.replace("ftpmirror.gnu.org", "ftp.gnu.org")

    filename = os.path.basename(url)
    base = filename.split('-')[0]

    msys2_package = MSYS2_PACKAGE_MAP.get(base)
    
    # Try installing with pacman if MSYS2 package is found and not for Ardour dependencies
    if msys2_package and "ardour.org" not in url:
        if check_msys2_package_installed(msys2_package):
            print(f"{msys2_package} is already installed. Skipping.")
            continue  # Skip downloading source if package is managed by MSYS2
        else:
            print(f"Required package '{msys2_package}' is not installed.")
            if try_install_msys2_package(msys2_package):
                continue  # Skip download and installation if pacman installation succeeded

    # Force download for dependencies coming from http://ardour.org/
    if "ardour.org" in url:
        print(f"Downloading {filename} from Ardour website (modified version)...")
        force_download = True
    else:
        force_download = not os.path.exists(os.path.join(DOWNLOAD_DIR, filename))

    # Download if necessary
    if force_download:
        print(f"Downloading {filename}...")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(os.path.join(DOWNLOAD_DIR, filename), "wb") as f:
                shutil.copyfileobj(r.raw, f)
    else:
        print(f"{filename} already exists. Skipping download.")

    # Extract the downloaded file
    extract_path = os.path.join(EXTRACT_DIR, os.path.splitext(filename)[0])
    if not os.path.exists(extract_path):
        print(f"Extracting {filename}...")
        try:
            if filename.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")):
                with tarfile.open(os.path.join(DOWNLOAD_DIR, filename), "r:*") as tar:
                    tar.extractall(path=extract_path)
            elif filename.endswith(".zip"):
                with zipfile.ZipFile(os.path.join(DOWNLOAD_DIR, filename), "r") as zip_ref:
                    zip_ref.extractall(path=extract_path)
            else:
                print(f"Unknown file format: {filename}")
                continue
        except Exception as e:
            print(f"Failed to extract {filename}: {e}")
            continue
    else:
        print(f"{filename} already extracted. Skipping.")

    # Install the extracted files if required
    if INSTALL:
        print(f"Installing {filename}...")
        original_dir = os.getcwd()
        inner_dir = os.path.join(extract_path, filename.split('-')[0] + '-' + filename.split('-')[1])
        os.chdir(inner_dir if os.path.exists(inner_dir) else extract_path)
        os.system(f"./configure --prefix={INSTALL_DIR}")
        os.system("make")
        os.system("make install")
        os.chdir(original_dir)
