#!/usr/bin/env python3
import json
import sys
import re
from pathlib import Path

def get_version(data):
    version_keys = ["version", "version-date", "version-semver", "version-string"]
    for key in version_keys:
        if key in data:
            return data[key]
    return "-"

def get_description(data):
    desc = data.get("description", "-")
    if isinstance(desc, list):
        return " ".join(desc)
    return desc

def main():
    repo_root = Path(__file__).resolve().parents[2]
    ports_dir = repo_root / "ports"
    readme_path = repo_root / "README.md"

    if not ports_dir.exists():
        print(f"Error: ports directory not found at {ports_dir}", file=sys.stderr)
        sys.exit(1)

    ports_data = []

    # Iterate over directories in ports
    for port_path in sorted(ports_dir.iterdir()):
        if port_path.is_dir():
            vcpkg_json_path = port_path / "vcpkg.json"
            if vcpkg_json_path.exists():
                try:
                    with open(vcpkg_json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    name = data.get("name", port_path.name)
                    version = get_version(data)
                    description = get_description(data)
                    homepage = data.get("homepage", "")
                    license_name = data.get("license", "-")

                    ports_data.append({
                        "name": name,
                        "version": version,
                        "description": description,
                        "homepage": homepage,
                        "license": license_name
                    })
                except Exception as e:
                    print(f"Warning: Failed to parse {vcpkg_json_path}: {e}", file=sys.stderr)

    # Generate markdown table
    table_lines = [
        "| Package | Version | Description | Homepage | License |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    for port in ports_data:
        name_cell = f"`{port['name']}`"
        version_cell = port['version']
        desc_cell = port['description']
        
        if port['homepage']:
            homepage_cell = f"[Link]({port['homepage']})"
        else:
            homepage_cell = "-"
            
        license_cell = port['license']
        
        table_lines.append(f"| {name_cell} | {version_cell} | {desc_cell} | {homepage_cell} | {license_cell} |")

    table_content = "\n".join(table_lines)

    # Read README.md
    if not readme_path.exists():
        print(f"Error: README.md not found at {readme_path}", file=sys.stderr)
        sys.exit(1)

    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()

    start_tag = "<!-- START_PORTS -->"
    end_tag = "<!-- END_PORTS -->"

    pattern = re.compile(rf"({re.escape(start_tag)})(.*?)({re.escape(end_tag)})", re.DOTALL)
    if not pattern.search(readme_content):
        print(f"Error: Could not find markers {start_tag} and {end_tag} in README.md", file=sys.stderr)
        sys.exit(1)

    new_content = pattern.sub(rf"\g<1>\n{table_content}\n\g<3>", readme_content)

    if readme_content != new_content:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("README.md has been successfully updated.")
    else:
        print("README.md is already up to date.")

if __name__ == "__main__":
    main()
