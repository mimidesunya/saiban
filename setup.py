import os
import urllib.request
import zipfile
import subprocess
import shutil
import sys
import re

DRIVER_URL = "https://dl.cssj.jp/release/driver/cti-python-3_0_0.zip"
ZIP_FILENAME = "cti-python-3_0_0.zip"
EXTRACT_DIR = "copper_driver"

def download_driver():
    print(f"Downloading driver from {DRIVER_URL}...")
    try:
        urllib.request.urlretrieve(DRIVER_URL, ZIP_FILENAME)
        print("Download complete.")
    except Exception as e:
        print(f"Failed to download driver: {e}")
        sys.exit(1)

def extract_driver():
    print(f"Extracting {ZIP_FILENAME}...")
    try:
        if os.path.exists(EXTRACT_DIR):
            shutil.rmtree(EXTRACT_DIR)
        
        with zipfile.ZipFile(ZIP_FILENAME, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)
        print("Extraction complete.")
    except Exception as e:
        print(f"Failed to extract driver: {e}")
        sys.exit(1)

def install_driver():
    print("Installing driver...")
    # Find the directory containing the 'code' folder which holds the package
    code_dir = None
    for root, dirs, files in os.walk(EXTRACT_DIR):
        if "code" in dirs:
            code_dir = os.path.join(root, "code")
            break
    
    if code_dir:
        print(f"Found code directory in {code_dir}")
        # Create a temporary setup.py
        setup_py_content = """
from setuptools import setup, find_packages

setup(
    name="cti-python",
    version="3.0.0",
    packages=find_packages(),
)
"""
        setup_py_path = os.path.join(code_dir, "setup.py")
        with open(setup_py_path, "w") as f:
            f.write(setup_py_content)
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "."], cwd=code_dir)
            print("Installation complete.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install driver: {e}")
            sys.exit(1)
    else:
        print("'code' directory not found in the extracted files.")
        sys.exit(1)

def cleanup():
    print("Cleaning up...")
    if os.path.exists(ZIP_FILENAME):
        os.remove(ZIP_FILENAME)
    if os.path.exists(EXTRACT_DIR):
        shutil.rmtree(EXTRACT_DIR)
    print("Cleanup complete.")

def generate_instructions():
    print("Generating AI instructions...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(base_dir, "src")
    
    # Templates are in src/templates
    templates_dirs = [
        os.path.join(src_dir, "templates")
    ]
    
    # Output directory is 'instructions' at root
    output_dir = os.path.join(base_dir, "instructions")
    instruction_file = os.path.join(src_dir, "base", "ai_instruction.md")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(instruction_file, "r", encoding="utf-8") as f:
        instruction_content = f.read()

    # Regex to find the HTML code block
    pattern = re.compile(r"(```html\n)([\s\S]*?)(\n```)")

    # Find HTML files
    template_files = []
    for t_dir in templates_dirs:
        if os.path.exists(t_dir):
            for root, dirs, files in os.walk(t_dir):
                for file in files:
                    if file.endswith(".html"):
                        template_files.append(os.path.join(root, file))

    for template_path in template_files:
        with open(template_path, "r", encoding="utf-8") as f:
            template_html = f.read()
        
        # Replace content
        new_content = pattern.sub(lambda m: m.group(1) + template_html + m.group(3), instruction_content)
        
        # Determine output filename
        # User wants "控訴状.md"
        filename = os.path.basename(template_path)
        name_without_ext = os.path.splitext(filename)[0]
        
        output_filename = f"{name_without_ext}.md"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Generated {output_filename}")

    print("Instruction generation complete.")

def is_driver_installed():
    try:
        # Check if cti-python is in the installed packages list
        result = subprocess.check_output([sys.executable, "-m", "pip", "list"], encoding='utf-8')
        return "cti-python" in result
    except subprocess.CalledProcessError:
        return False

if __name__ == "__main__":
    if not is_driver_installed():
        print("Driver not found. Installing...")
        download_driver()
        extract_driver()
        install_driver()
        cleanup()
    else:
        print("Driver (cti-python) is already installed.")

    generate_instructions()
