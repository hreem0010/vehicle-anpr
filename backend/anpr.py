import cv2
import numpy as np
import easyocr
import re

# Initialize EasyOCR reader once (loading it is slow, so we do it at module level)
# It will download the model on first run (~100MB), then cache it
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
print("Loading EasyOCR model... (this may take a moment on first run)")
reader = easyocr.Reader(['en'], gpu=False)  # gpu=False for CPU-only machines
print("EasyOCR ready.")


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """
    Convert image to grayscale and apply noise reduction.
    This makes it easier to detect edges and contours.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Bilateral filter: reduces noise while keeping edges sharp
    filtered = cv2.bilateralFilter(gray, 11, 17, 17)

    return filtered


def detect_plate_region(image: np.ndarray, preprocessed: np.ndarray):
    """
    Try to find the number plate region using edge detection + contours.
    Returns the cropped plate image if found, else returns the full image for OCR.
    """
    # Edge detection
    edges = cv2.Canny(preprocessed, 30, 200)

    # Find contours (outlines of shapes in image)
    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Sort contours by area, keep the largest 10
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

    plate_contour = None

    for contour in contours:
        # Approximate the contour to a simpler polygon
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.018 * perimeter, True)

        # A rectangle has 4 corners — number plates are rectangular
        if len(approx) == 4:
            plate_contour = approx
            break

    if plate_contour is not None:
        # Create a mask and extract just the plate region
        mask = np.zeros(preprocessed.shape, np.uint8)
        cv2.drawContours(mask, [plate_contour], 0, 255, -1)

        # Get bounding box of the plate
        x, y, w, h = cv2.boundingRect(plate_contour)

        # Sanity check: plate should be wider than tall, and not too small/large
        aspect_ratio = w / float(h)
        if 1.5 <= aspect_ratio <= 6.0 and w > 80 and h > 20:
            cropped_plate = image[y:y+h, x:x+w]
            return cropped_plate, True

    # If no plate region found, return full image and let OCR try anyway
    return image, False


def enhance_plate_for_ocr(plate_image: np.ndarray) -> np.ndarray:
    """
    Enhance the cropped plate image for better OCR accuracy.
    """
    # Resize to a larger size (OCR works better on bigger images)
    height, width = plate_image.shape[:2]
    scale = max(1, 200 // height)  # Ensure at least 200px height
    resized = cv2.resize(plate_image, (width * scale, height * scale), interpolation=cv2.INTER_CUBIC)

    # Convert to grayscale
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    # Apply threshold to make text clearer (black text on white background)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return thresh


def clean_plate_text(raw_text: str) -> str:
    """
    Clean up OCR output to extract a valid Indian number plate format.
    Indian plates follow: XX00XX0000 (e.g. MH12AB1234)
    """
    # Remove spaces, newlines, special characters
    cleaned = raw_text.replace(" ", "").replace("\n", "").upper()

    # Remove common OCR noise characters
    cleaned = re.sub(r'[^A-Z0-9]', '', cleaned)

    # Try to find an Indian plate pattern within the text
    # Pattern: 2 letters + 2 digits + 2 letters + 4 digits
    pattern = r'[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}'
    match = re.search(pattern, cleaned)

    if match:
        return match.group()

    # If no clean pattern found, return whatever we have (trimmed)
    return cleaned[:15] if len(cleaned) > 15 else cleaned


def extract_plate_text(image_bytes: bytes) -> dict:
    """
    Main function: takes raw image bytes, runs the full ANPR pipeline.
    Returns a dict with detected plate text and pipeline status info.
    """
    # Decode image bytes to OpenCV format
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        return {
            "success": False,
            "plate_text": None,
            "raw_ocr_text": None,
            "plate_detected": False,
            "error": "Could not decode image. Please upload a valid JPG or PNG."
        }

    # Step 1: Preprocess
    preprocessed = preprocess_image(image)

    # Step 2: Detect plate region
    plate_region, plate_found = detect_plate_region(image, preprocessed)

    # Step 3: Enhance for OCR
    enhanced = enhance_plate_for_ocr(plate_region)

    # Step 4: Run EasyOCR
    results = reader.readtext(enhanced, detail=0, paragraph=False)

    if not results:
        # Try OCR on the original full image as fallback
        results = reader.readtext(image, detail=0, paragraph=False)

    if not results:
        return {
            "success": False,
            "plate_text": None,
            "raw_ocr_text": None,
            "plate_detected": plate_found,
            "error": "OCR could not extract any text from the image."
        }

    # Combine all OCR results and clean
    raw_text = " ".join(results)
    cleaned_text = clean_plate_text(raw_text)

    return {
        "success": True,
        "plate_text": cleaned_text,
        "raw_ocr_text": raw_text,
        "plate_detected": plate_found,
        "error": None
    }