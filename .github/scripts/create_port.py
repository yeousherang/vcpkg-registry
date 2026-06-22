#!/usr/bin/env python3
import sys
import os
import json
import re
import hashlib
import urllib.request
import subprocess
from pathlib import Path

def parse_issue_body(body_text):
    data = {}
    current_key = None
    # normalize line endings
    body_text = body_text.replace('\r\n', '\n')
    lines = body_text.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('### '):
            current_key = line[4:].strip()
            data[current_key] = []
        elif current_key and line:
            # Skip placeholders and examples
            if line.startswith('_') or line.startswith('예:') or line.startswith('*'):
                continue
            data[current_key].append(line)
            
    cleaned_data = {}
    mapping = {
        "포트 이름 (Port Name)": "port_name",
        "버전 (Version)": "version",
        "버전 타입 (Version Type)": "version_type",
        "소스코드 아카이브 URL (Download URL)": "download_url",
        "SHA512 해시값 (선택 사항)": "sha512",
        "설명 (Description)": "description",
        "홈페이지 URL (Homepage URL)": "homepage",
        "라이선스 (License)": "license"
    }
    
    for key, val_list in data.items():
        mapped_key = mapping.get(key)
        if mapped_key:
            val = "\n".join(val_list).strip()
            if val.lower() in ["_no response_", "none", "n/a", ""]:
                cleaned_data[mapped_key] = ""
            else:
                cleaned_data[mapped_key] = val
                
    # Fill in default key properties if missing
    for k in mapping.values():
        if k not in cleaned_data:
            cleaned_data[k] = ""
            
    return cleaned_data

def calculate_sha512(url):
    print(f"Downloading archive from {url} to calculate SHA512...")
    sha512 = hashlib.sha512()
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        while True:
            chunk = response.read(1024 * 1024) # 1MB chunk
            if not chunk:
                break
            sha512.update(chunk)
    return sha512.hexdigest()

def write_port_files(ports_dir, port_name, info):
    port_path = ports_dir / port_name
    port_path.mkdir(parents=True, exist_ok=True)
    
    # vcpkg.json
    vcpkg_json = {
        "name": port_name,
        info["version_type"]: info["version"],
        "description": info["description"],
        "homepage": info["homepage"],
        "license": info["license"],
        "dependencies": [
            {
                "name": "vcpkg-cmake",
                "host": True
            },
            {
                "name": "vcpkg-cmake-config",
                "host": True
            }
        ]
    }
    
    with open(port_path / "vcpkg.json", "w", encoding="utf-8") as f:
        json.dump(vcpkg_json, f, indent=2, ensure_ascii=False)
        f.write("\n")
        
    # portfile.cmake
    download_url = info["download_url"]
    filename = download_url.split("/")[-1]
    if not filename.endswith((".tar.gz", ".zip", ".tgz", ".tar.xz")):
        filename = f"{port_name}-{info['version']}.tar.gz"
        
    portfile_content = f"""vcpkg_download_distfile(ARCHIVE
    URLS "{download_url}"
    FILENAME "{filename}"
    SHA512 {info['sha512']}
)

vcpkg_extract_source_archive(
    OUT_SOURCE_PATH SOURCE_PATH
    ARCHIVE "${{ARCHIVE}}"
)

vcpkg_cmake_configure(
    SOURCE_PATH "${{SOURCE_PATH}}"
)

vcpkg_cmake_install()
vcpkg_cmake_config_fixup()

file(REMOVE_RECURSE "${{CURRENT_PACKAGES_DIR}}/debug/include")
vcpkg_install_copyright(FILE_LIST "${{SOURCE_PATH}}/LICENSE" "${{SOURCE_PATH}}/COPYING")
"""
    with open(port_path / "portfile.cmake", "w", encoding="utf-8") as f:
        f.write(portfile_content)

def update_versions(repo_root, port_name, info):
    # 1. git add ports/port_name
    subprocess.run(["git", "add", f"ports/{port_name}"], cwd=repo_root, check=True)
    
    # 2. git write-tree
    res = subprocess.run(["git", "write-tree"], cwd=repo_root, capture_output=True, text=True, check=True)
    tree_sha = res.stdout.strip()
    
    # 3. git rev-parse {tree_sha}:ports/{port_name}
    res = subprocess.run(["git", "rev-parse", f"{tree_sha}:ports/{port_name}"], cwd=repo_root, capture_output=True, text=True, check=True)
    git_tree_hash = res.stdout.strip()
    
    print(f"Calculated git-tree hash: {git_tree_hash}")
    
    # 4. update versions/baseline.json
    baseline_path = repo_root / "versions" / "baseline.json"
    if baseline_path.exists():
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)
    else:
        baseline = {"default": {}}
        
    baseline["default"][port_name] = {
        "baseline": info["version"],
        "port-version": 0
    }
    
    # sort baseline keys
    baseline["default"] = dict(sorted(baseline["default"].items()))
    
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
        f.write("\n")
        
    # 5. update versions/<first-char>-/<port_name>.json
    first_char = port_name[0].lower()
    version_dir = repo_root / "versions" / f"{first_char}-"
    version_dir.mkdir(parents=True, exist_ok=True)
    
    version_file = version_dir / f"{port_name}.json"
    
    version_entry = {
        "git-tree": git_tree_hash,
        info["version_type"]: info["version"],
        "port-version": 0
    }
    
    if version_file.exists():
        with open(version_file, "r", encoding="utf-8") as f:
            v_data = json.load(f)
    else:
        v_data = {"versions": []}
        
    exists = False
    for v in v_data["versions"]:
        if v.get(info["version_type"]) == info["version"]:
            v["git-tree"] = git_tree_hash
            exists = True
            break
    if not exists:
        v_data["versions"].insert(0, version_entry)
        
    with open(version_file, "w", encoding="utf-8") as f:
        json.dump(v_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
        
    # 6. git add versions
    subprocess.run(["git", "add", "versions"], cwd=repo_root, check=True)

def main():
    if len(sys.argv) < 2:
        print("Usage: create_port.py <issue_body_file_path>", file=sys.stderr)
        sys.exit(1)
        
    issue_file = Path(sys.argv[1])
    if not issue_file.exists():
        print(f"Error: {issue_file} not found", file=sys.stderr)
        sys.exit(1)
        
    with open(issue_file, "r", encoding="utf-8") as f:
        body_text = f.read()
        
    info = parse_issue_body(body_text)
    
    # Validation
    required_fields = ["port_name", "version", "version_type", "download_url"]
    for f in required_fields:
        if not info[f]:
            print(f"Error: Missing required field '{f}'", file=sys.stderr)
            sys.exit(1)
            
    port_name = info["port_name"].strip().lower()
    # Normalize port name (alphanumeric, lowercase, hyphen)
    port_name = re.sub(r'[^a-z0-9\-]', '', port_name)
    if not port_name:
        print("Error: Port name contains invalid characters.", file=sys.stderr)
        sys.exit(1)
        
    if not info["version_type"]:
        info["version_type"] = "version"
        
    # Calculate SHA512 if not provided
    if not info["sha512"]:
        try:
            info["sha512"] = calculate_sha512(info["download_url"])
        except Exception as e:
            print(f"Error: Failed to download archive or calculate SHA512: {e}", file=sys.stderr)
            sys.exit(1)
            
    repo_root = Path(__file__).resolve().parents[2]
    ports_dir = repo_root / "ports"
    
    print(f"Creating files for port: {port_name}...")
    write_port_files(ports_dir, port_name, info)
    
    print(f"Updating registry versions for: {port_name}...")
    update_versions(repo_root, port_name, info)
    
    print(f"Port {port_name} created and versions updated successfully.")
    if "GITHUB_ENV" in os.environ:
        with open(os.environ["GITHUB_ENV"], "a") as f:
            f.write(f"PORT_NAME={port_name}\n")

if __name__ == "__main__":
    main()
