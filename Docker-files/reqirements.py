import subprocess
import sys
import os

def detect_distro():
    try:
        # For newer systems, /etc/os-release is standard
        with open("/etc/os-release") as f:
            lines = f.readlines()
        info = {}
        for line in lines:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                info[key] = value.strip('"')
        return info.get("ID", "").lower()
    except Exception:
        return ""

def install_pyaudio():
    distro = detect_distro()
    print(f"Detected distro: {distro}")

    try:
        if distro in ["ubuntu", "debian"]:
            subprocess.run(["sudo", "apt", "update"], check=True)
            subprocess.run(["sudo", "apt", "install", "-y", "python3-pyaudio", "portaudio19-dev"], check=True)
        elif distro in ["fedora", "rhel", "centos"]:
            subprocess.run(["sudo", "dnf", "install", "-y", "python3-pyaudio", "portaudio-devel"], check=True)
        elif distro in ["arch", "manjaro"]:
            subprocess.run(["sudo", "pacman", "-Sy", "--noconfirm", "python-pyaudio", "portaudio"], check=True)
        else:
            print("Unsupported distro or unable to detect.")
    except subprocess.CalledProcessError as e:
        print(f"Installation failed: {e}")

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
    install_pyaudio()
    install_requirements()
