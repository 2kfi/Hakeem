import os
import sys
import requests
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get_config


def download_file(url, destination):
    os.makedirs(os.path.dirname(destination), exist_ok=True)

    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))

    with (
        open(destination, "wb") as file,
        tqdm(
            desc=f"Downloading {os.path.basename(destination)}",
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar,
    ):
        for data in response.iter_content(chunk_size=16384):
            size = file.write(data)
            bar.update(size)


def main():
    config = get_config()

    print("--- Starting Model Download ---")
    print(f"[CONFIG] Download on startup: {config.models_download_on_startup}")
    print(f"[CONFIG] Storage path: {config.models_storage_path}")
    files_downloaded = 0
    skipped_local = 0

    model_urls = []
    model_urls.extend(config.get_stt_urls())
    model_urls.extend(config.get_tts_urls("en"))
    model_urls.extend(config.get_tts_urls("ar"))

    for url, local_path in model_urls:
        if not local_path:
            continue

        if not config.models_download_on_startup:
            if os.path.exists(local_path):
                print(f"[OK] Found: {local_path}")
            else:
                print(f"[MISSING] {local_path}")
            continue

        if not os.path.exists(local_path):
            print(f"\n[DOWNLOAD] {local_path}")
            print(f"[URL] {url}")
            try:
                download_file(url, local_path)
                files_downloaded += 1
            except Exception as e:
                print(f"[ERROR] Could not download: {e}")
        else:
            print(f"[OK] Found (skipping): {local_path}")
            skipped_local += 1

    if files_downloaded == 0:
        print(f"\nAll models present. Skipped {skipped_local} local models.")
    else:
        print(f"\nDone! Downloaded {files_downloaded} file(s).")


if __name__ == "__main__":
    main()
