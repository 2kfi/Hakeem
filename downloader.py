import os
import requests
from tqdm import tqdm

# Configuration for all your models
MODELS_TO_DOWNLOAD = {
    # 1. Faster Whisper Medium (Systran)
    "WHISPER_BIN": {
        "local_path": "models/whisper-medium/model.bin",
        "url": "https://huggingface.co/Systran/faster-whisper-medium/resolve/main/model.bin"
    },
    "WHISPER_CONFIG": {
        "local_path": "models/whisper-medium/config.json",
        "url": "https://huggingface.co/Systran/faster-whisper-medium/resolve/main/config.json"
    },
    "WHISPER_VOCAB": {
        "local_path": "models/whisper-medium/vocabulary.txt",
        "url": "https://huggingface.co/Systran/faster-whisper-medium/resolve/main/vocabulary.txt"
    },
    "WHISPER_TOKENIZER": {
        "local_path": "models/whisper-medium/tokenizer.json",
        "url": "https://huggingface.co/Systran/faster-whisper-medium/resolve/main/tokenizer.json"
    },
    
    # 2. TTS English (Cori - High Quality)
    "TTS_EN_MODEL": {
        "local_path": "models/TTS-CORI-EN/en_GB-cori-high.onnx",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/cori/high/en_GB-cori-high.onnx"
    },
    "TTS_EN_CONFIG": {
        "local_path": "models/TTS-CORI-EN/en_GB-cori-high.onnx.json",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/cori/high/en_GB-cori-high.onnx.json"
    },

    # 3. TTS Arabic (Kareem - Medium Quality)
    "TTS_AR_MODEL": {
        "local_path": "models/TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx"
    },
    "TTS_AR_CONFIG": {
        "local_path": "models/TTS-KAREEM-ARABIC/ar_JO-kareem-medium.onnx.json",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json"
    },
    # 4. AI Model and Porjecter
    "MEDGEMMA_MODEL": {
        "local_path": "models/MedGemma/MedGemma-3b-it-Q4_K_M.gguf",
        "url": "https://huggingface.co/2kfi/medgemma-4B-it-fine-tuned-gguf/resolve/main/MedGemma-3b-it-Q4_K_M.gguf"
    }
#    "MEDGEMMA_PROJ": {
#        "local_path": "models/MedGemma/MedGemma-mmproj.gguf",
#        "url": "https://huggingface.co/2kfi/medgemma-4B-it-fine-tuned-gguf/resolve/main/MedGemma-mmproj.gguf"
#    }
}

def download_file(url, destination):
    """Downloads a file and shows a progress bar."""
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    
    # Simple timeout and stream enabled for large files
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status() # This stops the script if the link is broken
    
    total_size = int(response.headers.get('content-length', 0))
    
    with open(destination, "wb") as file, tqdm(
        desc=f"Downloading {os.path.basename(destination)}",
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=16384): # larger chunk for speed
            size = file.write(data)
            bar.update(size)

def main():
    print("--- Starting Model Integrity Check ---")
    files_missing = 0

    for key, info in MODELS_TO_DOWNLOAD.items():
        if not os.path.exists(info["local_path"]):
            print(f"\n[MISSING] {info['local_path']}")
            try:
                download_file(info["url"], info["local_path"])
                files_missing += 1
            except Exception as e:
                print(f"[ERROR] Could not download {key}: {e}")
        else:
            print(f"[OK] Found: {info['local_path']}")

    if files_missing == 0:
        print("\nAll models are present. No downloads needed.")
    else:
        print(f"\nDone! Downloaded {files_missing} file(s).")

if __name__ == "__main__":
    main()