from fastapi import FastAPI
from pydantic import BaseModel
import base64
import cv2
import numpy as np
from skimage.restoration import wiener
from skimage import img_as_float
import logging

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# --- FastAPI Setup ---
app = FastAPI(title="Mammogram Image Cleaner API")

# --- Request / Response Models ---
class ImageRequest(BaseModel):
    image_data: str
    return_both: bool = False

class ImageItem(BaseModel):
    image_base64: str
    mime: str
    label: str

class ImageResponseSingle(BaseModel):
    image_base64: str
    mime: str

class ImageResponseMultiple(BaseModel):
    images: list[ImageItem]

# --- Image Processing Function ---
def process_mammogram(img: np.ndarray):
    """Applies Wiener + CLAHE filters."""
    # Wiener filter
    img_float = img_as_float(img)
    psf = np.ones((5, 5), dtype=np.float32) / 25.0
    w = wiener(img_float, psf, balance=0.1)
    w = np.nan_to_num(w, nan=0.0, posinf=1.0, neginf=0.0)
    w = np.clip(w, 0, 1)
    w_uint8 = (w * 255).astype(np.uint8)

    # CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    final = clahe.apply(w_uint8)

    # Encode Base64
    success_w, buffer_w = cv2.imencode(".png", w_uint8)
    success_final, buffer_final = cv2.imencode(".png", final)
    if not success_w or not success_final:
        raise ValueError("Failed to encode images.")

    w_base64 = base64.b64encode(buffer_w).decode("utf-8")
    final_base64 = base64.b64encode(buffer_final).decode("utf-8")

    return w_base64, final_base64

# --- API Endpoint ---
@app.post("/clean", response_model=dict)
def clean_image(req: ImageRequest):
    logging.info("Received request for mammogram cleaning.")
    try:
        # Decode Base64 image
        img_bytes = base64.b64decode(req.image_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            logging.error("Failed to decode image data.")
            return {"error": "Invalid image data: Failed to decode."}
        logging.info("Image decoded successfully.")
    except Exception as e:
        logging.error(f"Error decoding image data: {str(e)}", exc_info=True)
        return {"error": f"Server error decoding image data: {str(e)}"}

    try:
        w_base64, final_base64 = process_mammogram(img)
    except Exception as e:
        logging.error(f"Image processing failed: {str(e)}")
        return {"error": f"Image processing failed: {str(e)}"}

    if req.return_both:
        return {
            "images": [
                {"image_base64": w_base64, "mime": "image/png", "label": "Wiener only"},
                {"image_base64": final_base64, "mime": "image/png", "label": "Wiener + CLAHE"}
            ]
        }
    else:
        return {"image_base64": final_base64, "mime": "image/png"}

# --- Run with: uvicorn filename:app --host 0.0.0.0 --port 8000 ---
