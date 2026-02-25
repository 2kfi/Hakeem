from fastmcp import FastMCP
import logging
import os
import uuid

# Import the actual processing function from our refactored module
from processor import clean_mammogram_file

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# --- Directory Setup ---
PROCESSED_DIR = "processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

# --- MCP Setup ---
mcp = FastMCP("File-based Mammogram Cleaner")

@mcp.tool()
def clean_image_from_path(file_path: str) -> str:
    """
    Processes an image from a given local file path using a memory-efficient
    tiled method (Wiener + CLAHE filters) and returns the path to the
    processed image.

    Args:
        file_path: The absolute local path to the image file that needs to be cleaned.

    Returns:
        The absolute local path to the newly created processed image file.
    """
    logging.info(f"Received request to clean image from path: {file_path}")

    # --- Input Validation ---
    if not os.path.isabs(file_path):
        logging.error("The provided path is not an absolute path.")
        return "Error: Please provide an absolute file path."
    if not os.path.exists(file_path):
        logging.error(f"File does not exist at path: {file_path}")
        return f"Error: File not found at '{file_path}'"

    try:
        # --- Define Output Path ---
        file_id = str(uuid.uuid4())
        # It's good practice to maintain the original extension
        base, extension = os.path.splitext(os.path.basename(file_path))
        output_filename = f"{base}_{file_id}_processed{extension}"
        output_path = os.path.join(PROCESSED_DIR, output_filename)

        # --- Process the file ---
        logging.info(f"Processing {file_path} -> {output_path}")
        success = clean_mammogram_file(input_path=file_path, output_path=output_path)

        if success:
            final_path = os.path.abspath(output_path)
            logging.info(f"Processing successful. Result at: {final_path}")
            return final_path
        else:
            logging.error(f"Processing failed for file: {file_path}")
            return "Error: The image processing routine failed. Check server logs."

    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
        return f"An unexpected server error occurred: {str(e)}"


if __name__ == "__main__":
    HOST = "10.200.71.180"
    PORT = 4242 # A new port for the new MCP server
    logging.info(f"Starting File-Path MCP server on {HOST}:{PORT}")
    mcp.run(
        transport="http",
        host=HOST,
        port=PORT,
    )
