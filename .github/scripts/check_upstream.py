#!/usr/bin/env python3
import os
import re
import json
import sys
import urllib.request
import urllib.parse
import subprocess

# For security/authenticity we use GitHub API tokens if provided in env
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_API_URL = "https://api.github.com"
GITLAB_API_URL = "https://gitlab.com"

# Regex patterns for vcpkg cmake downloads
GITHUB_PATTERN = re.compile(r'vcpkg_from_github\s*\(\s*(.*?)\s*\)', re.DOTALL | re.IGNORECASE)
GITLAB_PATTERN = re.compile(r'vcpkg_from_gitlab\s*\(\s*(.*?)\s*\)', re.DOTALL | re.IGNORECASE)

def parse_block_args(block_content):
    # Strip comments
    lines = block_content.split('\n')
    cleaned = []
    for line in lines:
        if '#' in line:
            line = line.split('#')[0]
        cleaned.append(line.strip())
    content = ' '.join(cleaned)
    
    tokens = content.split()
    args = {}
    current_key = None
    for token in tokens:
        if token.isupper() and token in ['REPO', 'REF', 'SHA512', 'HEAD_REF', 'GITLAB_URL']:
            current_key = token
            args[current_key] = []
        elif current_key:
            args[current_key].append(token)
            
    for k in args:
        args[k] = ' '.join(args[k])
    return args

def make_github_request(url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "vcpkg-registry-bot")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    return req

def get_latest_commit_github(repo, ref):
    url = f"{GITHUB_API_URL}/repos/{repo}/commits/{ref}"
    req = make_github_request(url)
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode())
            return data['sha'], data['commit']['committer']['date'][:10]
    except Exception as e:
        print(f"Error fetching github commit for {repo}: {e}")
        return None, None

def get_latest_tag_github(repo):
    url = f"{GITHUB_API_URL}/repos/{repo}/tags"
    req = make_github_request(url)
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode())
            if data:
                latest = data[0]
                return latest['name'].lstrip('v'), latest['commit']['sha']
    except Exception as e:
        print(f"Error fetching github tags for {repo}: {e}")
        return None, None

def get_latest_commit_gitlab(gitlab_url, repo, ref):
    encoded_repo = urllib.parse.quote_plus(repo)
    if not gitlab_url:
        gitlab_url = GITLAB_API_URL
    url = f"{gitlab_url}/api/v4/projects/{encoded_repo}/repository/commits/{ref}"
    req = urllib.request.Request(url, headers={"User-Agent": "vcpkg-registry-bot"})
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode())
            return data['id'], data['committed_date'][:10]
    except Exception as e:
        print(f"Error fetching gitlab commit for {repo}: {e}")
        return None, None

def get_latest_tag_gitlab(gitlab_url, repo):
    encoded_repo = urllib.parse.quote_plus(repo)
    if not gitlab_url:
        gitlab_url = GITLAB_API_URL
    url = f"{gitlab_url}/api/v4/projects/{encoded_repo}/repository/tags"
    req = urllib.request.Request(url, headers={"User-Agent": "vcpkg-registry-bot"})
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode())
            if data:
                latest = data[0]
                return latest['name'].lstrip('v'), latest['commit']['id']
    except Exception as e:
        print(f"Error fetching gitlab tags for {repo}: {e}")
        return None, None

def get_actual_sha512(port_name):
    # Run vcpkg install to get the correct hash from the error message
    cmd = ["vcpkg", "install", port_name, "--overlay-ports=ports", "--binarysource=clear"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + "\n" + result.stderr
    
    # Match expected sha512 from errors
    match = re.search(r'please change the expected SHA512 to:\s*([a-f0-9]{128})', output, re.IGNORECASE)
    if match:
        return match.group(1)
    match2 = re.search(r'Actual hash:\s*([a-f0-9]{128})', output, re.IGNORECASE)
    if match2:
        return match2.group(1)
    return None

def update_port_files(port_name, port_dir, new_version, version_field, new_ref, is_github, block_content, parsed_args):
    # Update vcpkg.json
    vcpkg_json_path = os.path.join(port_dir, "vcpkg.json")
    with open(vcpkg_json_path, 'r', encoding='utf-8') as f:
        vcpkg_data = json.load(f)
    
    old_version = vcpkg_data.get(version_field)
    vcpkg_data[version_field] = new_version
    # reset port-version if exists
    if "port-version" in vcpkg_data:
        vcpkg_data["port-version"] = 0
        
    with open(vcpkg_json_path, 'w', encoding='utf-8') as f:
        json.dump(vcpkg_data, f, indent=2)
        f.write('\n')

    # Update portfile.cmake
    portfile_path = os.path.join(port_dir, "portfile.cmake")
    with open(portfile_path, 'r', encoding='utf-8') as f:
        portfile_content = f.read()

    # Reconstruct the download block with a dummy SHA512
    old_ref = parsed_args['REF']
    old_sha = parsed_args['SHA512']
    dummy_sha = "0" * 128
    
    # Simple replacement in the original file
    block_pattern = GITHUB_PATTERN if is_github else GITLAB_PATTERN
    match = block_pattern.search(portfile_content)
    if not match:
        raise Exception("Could not find the download block in portfile.cmake during update")
        
    original_block = match.group(0)
    # Replace old_ref with new_ref and old_sha with dummy_sha in the block
    new_block = original_block.replace(old_ref, new_ref).replace(old_sha, dummy_sha)
    portfile_content = portfile_content.replace(original_block, new_block)
    
    with open(portfile_path, 'w', encoding='utf-8') as f:
        f.write(portfile_content)

    print(f"[{port_name}] Wrote dummy SHA512. Triggering vcpkg build to obtain actual SHA512...")
    
    # Run vcpkg to get the correct SHA512
    actual_sha = get_actual_sha512(port_name)
    if not actual_sha:
        # Revert changes if we couldn't get the hash
        vcpkg_data[version_field] = old_version
        with open(vcpkg_json_path, 'w', encoding='utf-8') as f:
            json.dump(vcpkg_data, f, indent=2)
            f.write('\n')
        with open(portfile_path, 'w', encoding='utf-8') as f:
            f.write(portfile_content.replace(new_block, original_block))
        raise Exception(f"Failed to resolve SHA512 for {port_name}")

    # Replace dummy SHA with the actual SHA
    with open(portfile_path, 'r', encoding='utf-8') as f:
        portfile_content = f.read()
    
    # We must match again as it might have changed
    match = block_pattern.search(portfile_content)
    updated_block = match.group(0)
    final_block = updated_block.replace(dummy_sha, actual_sha)
    portfile_content = portfile_content.replace(updated_block, final_block)
    
    with open(portfile_path, 'w', encoding='utf-8') as f:
        f.write(portfile_content)
        
    print(f"[{port_name}] Successfully resolved SHA512: {actual_sha}")
    return old_version

def main():
    ports_dir = "ports"
    if not os.path.isdir(ports_dir):
        print("ports/ directory not found in the current workspace.")
        sys.exit(1)

    updated_ports = []

    for port_name in os.listdir(ports_dir):
        port_dir = os.path.join(ports_dir, port_name)
        if not os.path.isdir(port_dir):
            continue
            
        portfile_path = os.path.join(port_dir, "portfile.cmake")
        vcpkg_json_path = os.path.join(port_dir, "vcpkg.json")
        
        if not os.path.exists(portfile_path) or not os.path.exists(vcpkg_json_path):
            continue

        print(f"Checking port: {port_name}...")
        
        # Read portfile.cmake
        with open(portfile_path, 'r', encoding='utf-8') as f:
            portfile_content = f.read()

        is_github = True
        match = GITHUB_PATTERN.search(portfile_content)
        if not match:
            is_github = False
            match = GITLAB_PATTERN.search(portfile_content)
            
        if not match:
            print(f"[{port_name}] No supported download block (vcpkg_from_github/gitlab) found. Skipping.")
            continue

        block_content = match.group(1)
        parsed_args = parse_block_args(block_content)
        
        if 'REPO' not in parsed_args or 'REF' not in parsed_args or 'SHA512' not in parsed_args:
            print(f"[{port_name}] Incomplete download arguments. Skipping.")
            continue

        repo = parsed_args['REPO']
        current_ref = parsed_args['REF']
        head_ref = parsed_args.get('HEAD_REF', 'master')
        gitlab_url = parsed_args.get('GITLAB_URL', '')

        # Read vcpkg.json to determine version style
        with open(vcpkg_json_path, 'r', encoding='utf-8') as f:
            vcpkg_data = json.load(f)

        version_field = None
        if "version-date" in vcpkg_data:
            version_field = "version-date"
        elif "version" in vcpkg_data:
            version_field = "version"
        else:
            print(f"[{port_name}] Unsupported version format (no version or version-date). Skipping.")
            continue

        new_ref = None
        new_version = None

        if version_field == "version-date":
            # Track branch HEAD commit
            if is_github:
                new_ref, new_version = get_latest_commit_github(repo, head_ref)
            else:
                new_ref, new_version = get_latest_commit_gitlab(gitlab_url, repo, head_ref)
        elif version_field == "version":
            # Track tags
            if is_github:
                new_version, new_ref = get_latest_tag_github(repo)
            else:
                new_version, new_ref = get_latest_tag_gitlab(gitlab_url, repo)
                
        if not new_ref or not new_version:
            print(f"[{port_name}] Could not retrieve upstream information. Skipping.")
            continue

        if current_ref == new_ref:
            print(f"[{port_name}] Up-to-date (Ref: {current_ref}).")
            continue

        print(f"[{port_name}] Update available! Current Ref: {current_ref} -> New Ref: {new_ref} ({new_version})")
        
        try:
            old_version = update_port_files(
                port_name=port_name,
                port_dir=port_dir,
                new_version=new_version,
                version_field=version_field,
                new_ref=new_ref,
                is_github=is_github,
                block_content=block_content,
                parsed_args=parsed_args
            )
            updated_ports.append({
                "name": port_name,
                "old_version": old_version,
                "new_version": new_version,
                "old_ref": current_ref,
                "new_ref": new_ref
            })
        except Exception as e:
            print(f"[{port_name}] Failed to update: {e}")

    # Process all updated ports
    if not updated_ports:
        print("All ports are up-to-date. No updates needed.")
        sys.exit(0)

    # Git operations and PR creation
    for port in updated_ports:
        name = port["name"]
        old_v = port["old_version"]
        new_v = port["new_version"]
        
        branch_name = f"update-{name}-{new_v}"
        print(f"Creating branch and PR for {name} ({old_v} -> {new_v})...")
        
        # Git checkout new branch
        subprocess.run(["git", "checkout", "-b", branch_name])
        
        # Add files
        subprocess.run(["git", "add", f"ports/{name}/"])
        subprocess.run(["git", "commit", "-m", f"[{name}] Update to version {new_v}"])
        
        # Run vcpkg database update
        subprocess.run([
            "vcpkg", 
            "--x-builtin-ports-root=./ports", 
            "--x-builtin-registry-versions-dir=./versions", 
            "x-add-version", 
            name
        ])
        
        subprocess.run(["git", "add", "versions/"])
        subprocess.run(["git", "commit", "-m", f"[{name}] Update versions database for version {new_v}"])
        
        # Push and Create PR via GitHub CLI
        # (Assuming GitHub CLI 'gh' is installed and authenticated in GitHub Actions environment)
        push_res = subprocess.run(["git", "push", "origin", branch_name, "--force"])
        if push_res.returncode == 0:
            pr_title = f"Update port '{name}' to {new_v}"
            pr_body = (
                f"Automated update for port **{name}**.\n\n"
                f"- **Upstream version/date**: {old_v} -> {new_v}\n"
                f"- **Git Reference**: `{port['old_ref'][:8]}` -> `{port['new_ref'][:8]}`\n\n"
                f"This PR was automatically generated by the Upstream Check workflow."
            )
            subprocess.run([
                "gh", "pr", "create", 
                "--title", pr_title, 
                "--body", pr_body, 
                "--head", branch_name, 
                "--base", "main"
            ])
            print(f"PR successfully created for {name}.")
        else:
            print(f"Failed to push branch {branch_name} to origin.")
            
        # Switch back to main branch
        subprocess.run(["git", "checkout", "main"])

if __name__ == "__main__":
    main()
