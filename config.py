"""
Configuration settings for the Automatic Attendance System.
All constants and settings are centralized here.
"""

import os

# ─── Base Paths ───────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "attendance.db")
KNOWN_FACES_DIR = os.path.join(BASE_DIR, "known_faces")
ENCODINGS_DIR = os.path.join(BASE_DIR, "encodings")
ENCODINGS_FILE = os.path.join(ENCODINGS_DIR, "face_encodings.pkl")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# ─── Ensure directories exist ────────────────────────────────
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
os.makedirs(ENCODINGS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# ─── OpenCV DNN Model Paths ──────────────────────────────────
# YuNet face detector (~230KB ONNX model)
FACE_DETECTOR_MODEL = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
FACE_DETECTOR_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

# SFace face recognizer (~37MB ONNX model, produces 128-d embeddings)
FACE_RECOGNIZER_MODEL = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")
FACE_RECOGNIZER_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

# ─── Face Recognition Settings ───────────────────────────────
# Cosine similarity threshold for SFace (higher = stricter)
# SFace recommended: 0.363 (default), we use 0.40 for college setting
FACE_MATCH_THRESHOLD = 0.40

# Minimum detection confidence for YuNet (0.0 - 1.0)
FACE_DETECTION_CONFIDENCE = 0.7

# ─── Camera / Scanning Settings ──────────────────────────────
# How often the browser sends a frame to the server (in milliseconds)
SCAN_INTERVAL_MS = 1000  # 1 second

# ─── Time Windows for Working Mode ───────────────────────────
# Each tuple: (start_hour, start_minute, end_hour, end_minute, label)
TIME_WINDOWS = [
    (10, 0, 10, 15, "10:00 AM - 10:15 AM"),
    (11, 0, 11, 15, "11:00 AM - 11:15 AM"),
    (12, 0, 12, 15, "12:00 PM - 12:15 PM"),
    (14, 0, 14, 15, "2:00 PM - 2:15 PM"),
    (15, 0, 15, 15, "3:00 PM - 3:15 PM"),
    (16, 0, 16, 15, "4:00 PM - 4:15 PM"),
]

# ─── App Settings ─────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 5000))
