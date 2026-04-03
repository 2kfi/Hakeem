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

    if not config.models_download_on_startup:
        print("[CONFIG] Model download on startup disabled.")
        _check_models(config)
        return

    print("--- Starting Model Integrity Check ---")
    files_missing = 0

    model_urls = []
    model_urls.extend(config.get_whisper_urls())
    model_urls.extend(config.get_tts_en_urls())
    model_urls.extend(config.get_tts_ar_urls())
    model_urls.extend(config.get_medgemma_urls())

    for url, local_path in model_urls:
        if not os.path.exists(local_path):
            print(f"\n[MISSING] {local_path}")
            try:
                download_file(url, local_path)
                files_missing += 1
            except Exception as e:
                print(f"[ERROR] Could not download: {e}")
        else:
            print(f"[OK] Found: {local_path}")

    if files_missing == 0:
        print("\nAll models are present. No downloads needed.")
    else:
        print(f"\nDone! Downloaded {files_missing} file(s).")


def _check_models(config):
    print("--- Checking Model Integrity ---")

    model_urls = []
    model_urls.extend(config.get_whisper_urls())
    model_urls.extend(config.get_tts_en_urls())
    model_urls.extend(config.get_tts_ar_urls())
    model_urls.extend(config.get_medgemma_urls())

    all_present = True
    for url, local_path in model_urls:
        if not os.path.exists(local_path):
            print(f"[MISSING] {local_path}")
            all_present = False
        else:
            print(f"[OK] Found: {local_path}")

    if all_present:
        print("\nAll models are present.")
    else:
        print(
            "\nSome models are missing. Enable download or provide models via volume."
        )


if __name__ == "__main__":
    main()
