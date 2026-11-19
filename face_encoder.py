"""
Face Encoder module for the Automatic Attendance System.
Uses OpenCV DNN SFace model for 128-d face embeddings.
No dlib or face_recognition dependency needed.
"""

import os
import pickle
import urllib.request
import numpy as np
import cv2
from config import (
    KNOWN_FACES_DIR, ENCODINGS_FILE,
    FACE_RECOGNIZER_MODEL, FACE_RECOGNIZER_URL,
    FACE_MATCH_THRESHOLD
)

# ─── Model Download ──────────────────────────────────────────

def _download_model(url, dest_path):
    """Download a model file if it doesn't exist locally."""
    if os.path.exists(dest_path):
        return
    print(f"📥 Downloading model: {os.path.basename(dest_path)}...")
    urllib.request.urlretrieve(url, dest_path)
    print(f"✅ Model downloaded: {os.path.basename(dest_path)}")


# ─── SFace Recognizer (lazy-loaded singleton) ────────────────

_recognizer = None


def _get_recognizer():
    """Get or create the SFace face recognizer."""
    global _recognizer
    if _recognizer is None:
        _download_model(FACE_RECOGNIZER_URL, FACE_RECOGNIZER_MODEL)
        _recognizer = cv2.FaceRecognizerSF.create(
            FACE_RECOGNIZER_MODEL, ""
        )
    return _recognizer


# ─── In-memory cache of known face encodings ─────────────────
# Structure: { "roll_no": numpy_array_128d, ... }
_known_encodings = {}


def load_encodings():
    """Load all known face encodings from the pickle file into memory."""
    global _known_encodings
    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, "rb") as f:
            _known_encodings = pickle.load(f)
    else:
        _known_encodings = {}
    return _known_encodings


def save_encodings():
    """Persist the in-memory encodings to the pickle file."""
    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump(_known_encodings, f)


def get_known_count():
    """Return the number of known face encodings in memory."""
    return len(_known_encodings)


def encode_face(image_bgr, face):
    """
    Compute the 128-dimensional face embedding using SFace.
    Args:
        image_bgr: BGR numpy array (full image)
        face: YuNet face detection result (1D array with 14 values)
    Returns:
        128-d numpy array (feature vector), or None if encoding fails.
    """
    try:
        recognizer = _get_recognizer()
        # Align and crop the face for the recognizer
        aligned = recognizer.alignCrop(image_bgr, face)
        # Extract the 128-d feature vector
        feature = recognizer.feature(aligned)
        return feature.flatten()
    except Exception as e:
        print(f"Face encoding error: {e}")
        return None


def add_face_encoding(roll_no, encoding):
    """
    Add a new face encoding to the in-memory cache and persist to disk.
    Overwrites if roll_no already exists.
    """
    _known_encodings[roll_no] = encoding
    save_encodings()


def remove_face_encoding(roll_no):
    """Remove a face encoding from cache and disk."""
    if roll_no in _known_encodings:
        del _known_encodings[roll_no]
        save_encodings()
        return True
    return False


def match_face(encoding):
    """
    Compare an unknown face encoding against all known encodings using cosine similarity.
    Returns:
        (roll_no, score) if a match is found above threshold.
        (None, None) if no match.
    """
    if not _known_encodings:
        return None, None

    recognizer = _get_recognizer()
    best_roll = None
    best_score = -1.0

    # Reshape encoding for OpenCV's match function
    enc = encoding.reshape(1, -1)

    for roll_no, known_enc in _known_encodings.items():
        known = known_enc.reshape(1, -1)
        # Cosine similarity: higher = more similar (max 1.0)
        score = recognizer.match(enc, known, cv2.FaceRecognizerSF_FR_COSINE)

        if score > best_score:
            best_score = score
            best_roll = roll_no

    if best_score >= FACE_MATCH_THRESHOLD:
        return best_roll, float(best_score)

    return None, None


def save_cropped_face(roll_no, image_bgr, face):
    """
    Crop the detected face from the image and save it as a JPEG.
    Args:
        roll_no: Student roll number (used as filename)
        image_bgr: Full BGR image
        face: YuNet face detection result
    Returns:
        The saved file path.
    """
    x, y, w, h = (int(v) for v in face[:4])
    img_h, img_w = image_bgr.shape[:2]

    # Add padding around the face
    pad = 30
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(img_w, x + w + pad)
    y2 = min(img_h, y + h + pad)

    face_crop = image_bgr[y1:y2, x1:x2]
    filepath = os.path.join(KNOWN_FACES_DIR, f"{roll_no}.jpg")
    cv2.imwrite(filepath, face_crop)
    return filepath


# ─── Load encodings on import ────────────────────────────────
load_encodings()
