"""Image data tests that never require the webcam or OpenCV model weights."""
import base64

import cv2
import numpy as np

from camera import decode_base64_image, get_face_box, draw_face_boxes


def test_decode_valid_png_with_data_url():
    original = np.zeros((12, 16, 3), dtype=np.uint8)
    original[:, :, 1] = 100
    ok, encoded = cv2.imencode(".png", original)
    assert ok
    image = decode_base64_image("data:image/png;base64," + base64.b64encode(encoded).decode())
    assert np.array_equal(image, original)


def test_decode_invalid_input_returns_none():
    assert decode_base64_image("this is not a picture") is None


def test_get_face_box_converts_to_integers():
    assert get_face_box([1.9, 2.7, 5.4, 7.1] + [0.0] * 10) == (1, 2, 5, 7)


def test_draw_face_box_returns_encoded_jpeg():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    face = np.array([20, 30, 40, 40] + [0] * 10)
    result = draw_face_boxes(image, [face], ["Test"])
    assert isinstance(result, str)
    assert base64.b64decode(result).startswith(b"\xff\xd8")


def test_decode_raw_base64_without_data_url():
    ok, encoded = cv2.imencode(".png", np.full((8, 8, 3), 42, dtype=np.uint8))
    assert ok
    decoded = decode_base64_image(base64.b64encode(encoded).decode("ascii"))
    assert decoded.shape == (8, 8, 3)
    assert np.all(decoded == 42)


def test_detector_with_no_faces_uses_stub_not_real_model(monkeypatch):
    import camera

    class DummyDetector:
        def setInputSize(self, size):
            assert size == (16, 8)

        def detect(self, image):
            return None, None

    monkeypatch.setattr(camera, "_get_detector", lambda: DummyDetector())
    assert camera.detect_faces(np.zeros((8, 16, 3), dtype=np.uint8)) == []


def test_detector_returns_faces_from_fake_model(monkeypatch):
    import camera
    expected = np.array([[2, 3, 10, 12] + [0] * 10], dtype=np.float32)

    class DummyDetector:
        def setInputSize(self, size):
            assert size == (16, 8)

        def detect(self, image):
            return None, expected

    monkeypatch.setattr(camera, "_get_detector", lambda: DummyDetector())
    assert np.array_equal(camera.detect_faces(np.zeros((8, 16, 3), dtype=np.uint8)), expected)
