"""
Camera module for the Automatic Attendance System.
Uses OpenCV DNN YuNet model for face detection from browser-captured images.
No dlib or face_recognition dependency needed.
"""

import base64
import os
import urllib.request
import numpy as np
import cv2
from config import (
    FACE_DETECTOR_MODEL, FACE_DETECTOR_URL,
    FACE_DETECTION_CONFIDENCE
)

# ─── Model Download ──────────────────────────────────────────

def _download_model(url, dest_path):
    """Download a model file if it doesn't exist locally."""
    if os.path.exists(dest_path):
        return
    print(f"📥 Downloading model: {os.path.basename(dest_path)}...")
    urllib.request.urlretrieve(url, dest_path)
    print(f"✅ Model downloaded: {os.path.basename(dest_path)}")


# ─── YuNet Face Detector (lazy-loaded singleton) ─────────────

_detector = None


def _get_detector():
    """Get or create the YuNet face detector."""
    global _detector
    if _detector is None:
        _download_model(FACE_DETECTOR_URL, FACE_DETECTOR_MODEL)
        _detector = cv2.FaceDetectorYN.create(
            FACE_DETECTOR_MODEL,
            "",
            (320, 320),  # default input size, will be overridden per image
            FACE_DETECTION_CONFIDENCE,  # confidence threshold
            0.3,  # NMS threshold
        )
    return _detector


# ─── Image Decoding ──────────────────────────────────────────

def decode_base64_image(base64_string):
    """
    Decode a base64 image string (from browser canvas) to a BGR numpy array.
    Handles both raw base64 and data-URL prefixed strings.
    Returns the BGR image as a numpy array, or None if decoding fails.
    """
    try:
        if "," in base64_string:
            base64_string = base64_string.split(",", 1)[1]

        img_bytes = base64.b64decode(base64_string)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img_bgr
    except Exception:
        return None


# ─── Face Detection ──────────────────────────────────────────

def detect_faces(image_bgr):
    """
    Detect faces in a BGR image using the YuNet detector.

    Returns:
        List of face arrays. Each face is a 1D array with 14 values:
        [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm]
        where re=right_eye, le=left_eye, nt=nose_tip, rcm/lcm=right/left_corner_mouth.
        Returns empty list if no faces detected.
    """
    detector = _get_detector()
    h, w = image_bgr.shape[:2]
    detector.setInputSize((w, h))

    _, faces = detector.detect(image_bgr)

    if faces is None:
        return []

    return faces


def get_face_box(face):
    """
    Extract the bounding box (x, y, w, h) from a YuNet face detection result.
    Returns (x, y, w, h) as integers.
    """
    return tuple(int(v) for v in face[:4])


# ─── Annotated Image ─────────────────────────────────────────

def draw_face_boxes(image_bgr, faces, names=None):
    """
    Draw bounding boxes and optional name labels on detected faces.
    Returns the annotated image as a base64-encoded JPEG string.
    """
    img = image_bgr.copy()

    for i, face in enumerate(faces):
        x, y, w, h = get_face_box(face)

        # Draw rectangle
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Draw name label
        label = "Unknown"
        if names and i < len(names) and names[i]:
            label = names[i]

        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
        cv2.rectangle(img, (x, y - 25), (x + label_size[0] + 10, y), (0, 255, 0), cv2.FILLED)
        cv2.putText(img, label, (x + 5, y - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    _, buffer = cv2.imencode(".jpg", img)
    return base64.b64encode(buffer).decode("utf-8")
