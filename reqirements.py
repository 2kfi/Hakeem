import subprocess
import sys
import os

def install_requirements():
    req_file = "requirements.txt"
    if not os.path.exists(req_file):
        print(f"[!] {req_file} not found.")
        return

    print(f"--- Checking dependencies from {req_file} ---")
    
    # We use subprocess.run with capture_output=True to see the REAL error
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_file],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("[✓] Dependencies satisfied.")
    else:
        print("\n" + "="*30)
        print("PIP INSTALLATION FAILED")
        print("="*30)
        print("ERROR OUTPUT:")
        print(result.stderr) # This prints the actual pip error
        print("="*30)
        # Stop the script here so you can fix the error
        sys.exit(1)

if __name__ == "__main__":
    install_requirements()