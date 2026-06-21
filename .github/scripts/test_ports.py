#!/usr/bin/env python3
import os
import sys
import subprocess
import time

def test_port(port_name):
    print(f"Testing port {port_name}...")
    start_time = time.time()
    # Run vcpkg install to verify
    cmd = ["vcpkg", "install", port_name, "--overlay-ports=ports", "--binarysource=clear"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start_time
    
    success = (result.returncode == 0)
    error_summary = ""
    if not success:
        # Extract meaningful error messages
        lines = (result.stdout + "\n" + result.stderr).split('\n')
        error_lines = [l for l in lines if "error" in l.lower() or "failed" in l.lower() or "warning" in l.lower()]
        error_summary = "\n".join(error_lines[-10:])
        if not error_summary.strip():
            error_summary = "\n".join(lines[-15:])
            
    return {
        "name": port_name,
        "success": success,
        "duration": f"{duration:.2f}s",
        "error_summary": error_summary
    }

def main():
    ports_dir = "ports"
    if not os.path.isdir(ports_dir):
        print("ports/ directory not found.")
        sys.exit(1)
        
    # If specific ports are provided via arguments, test only those
    target_ports = sys.argv[1:] if len(sys.argv) > 1 else [d for d in os.listdir(ports_dir) if os.path.isdir(os.path.join(ports_dir, d))]
    
    results = []
    for port_name in target_ports:
        port_dir = os.path.join(ports_dir, port_name)
        if not os.path.isdir(port_dir):
            continue
        results.append(test_port(port_name))
        
    # Generate Markdown Report
    report = []
    report.append("### 🧪 Vcpkg Port Build Test Results\n")
    report.append("| Port Name | Status | Duration | Details |")
    report.append("| :--- | :--- | :--- | :--- |")
    
    all_success = True
    for r in results:
        status_emoji = "✅ Success" if r["success"] else "❌ Failed"
        if not r["success"]:
            all_success = False
            details = f"<details><summary>Click to view error log</summary>\\n\\n```\\n{r['error_summary']}\\n```\\n</details>"
        else:
            details = "Built successfully."
            
        report.append(f"| **{r['name']}** | {status_emoji} | {r['duration']} | {details} |")
        
    report_text = "\n".join(report)
    
    with open("test-results.md", "w", encoding="utf-8") as f:
        f.write(report_text)
        
    print("\nTest Summary:")
    print(report_text)
    
    if not all_success:
        sys.exit(1)
        
if __name__ == "__main__":
    main()
