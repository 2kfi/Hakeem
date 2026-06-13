import logging
import os
import tarfile

from core.config import RAGSettings

logger = logging.getLogger(__name__)


def has_onnx_model(model_dir: str) -> bool:
    return os.path.exists(os.path.join(model_dir, "onnx", "model.onnx"))


def download_onnx_model(settings: RAGSettings) -> bool:
    if has_onnx_model(settings.model_dir):
        logger.info(f"ONNX model already exists: {settings.model_dir}/onnx/model.onnx")
        return True

    os.makedirs(settings.model_dir, exist_ok=True)
    tar_path = os.path.join(settings.model_dir, "onnx.tar.gz")

    if settings.hf_repo:
        logger.info(f"Downloading ONNX model from HuggingFace: {settings.hf_repo}")
        try:
            from huggingface_hub import hf_hub_download
            downloaded = hf_hub_download(
                repo_id=settings.hf_repo,
                filename=settings.hf_filename,
                local_dir=settings.model_dir,
                local_dir_use_symlinks=False,
            )
            if downloaded.endswith(".tar.gz"):
                tar_path = downloaded
            else:
                logger.info(f"ONNX model ready: {downloaded}")
                return True
        except Exception as e:
            logger.error(f"HuggingFace download failed: {e}")
            return False
    else:
        url = settings.download_url or (
            f"https://chroma-onnx-models.s3.amazonaws.com/{settings.embedding_model}/onnx.tar.gz"
        )
        logger.info(f"Downloading ONNX model from {url}")
        import httpx
        with httpx.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            with open(tar_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)

    logger.info(f"Extracting to {settings.model_dir}...")
    with tarfile.open(tar_path) as tar:
        tar.extractall(path=settings.model_dir)
    os.remove(tar_path)
    logger.info(f"ONNX model ready: {settings.model_dir}/onnx/model.onnx")
    return True
