"""Face matching behavior: fake model outputs, never downloads real models."""
import numpy as np


def test_match_face_returns_none_with_empty_cache(database_module, monkeypatch):
    import face_encoder
    monkeypatch.setattr(face_encoder, "_known_encodings", {})
    assert face_encoder.match_face(np.ones(3)) == (None, None)


def test_match_face_selects_best_valid_candidate(database_module, monkeypatch):
    import face_encoder

    class FakeRecognizer:
        def match(self, actual, known, metric):
            return float(known[0, 0])

    monkeypatch.setattr(face_encoder, "_known_encodings", {
        "LOW": np.array([0.2, 0, 0]),
        "HIGH": np.array([0.85, 0, 0]),
    })
    monkeypatch.setattr(face_encoder, "_get_recognizer", lambda: FakeRecognizer())
    assert face_encoder.match_face(np.ones(3)) == ("HIGH", 0.85)


def test_match_face_rejects_candidate_below_threshold(database_module, monkeypatch):
    import face_encoder

    class FakeRecognizer:
        def match(self, actual, known, metric):
            return 0.01

    monkeypatch.setattr(face_encoder, "_known_encodings", {"TEST": np.ones(3)})
    monkeypatch.setattr(face_encoder, "_get_recognizer", lambda: FakeRecognizer())
    assert face_encoder.match_face(np.ones(3)) == (None, None)


def test_encode_face_returns_none_when_model_fails(database_module, monkeypatch):
    import face_encoder

    def fail():
        raise RuntimeError("Model unavailable")

    monkeypatch.setattr(face_encoder, "_get_recognizer", fail)
    assert face_encoder.encode_face(None, None) is None


def test_encode_face_flattens_feature_vector(database_module, monkeypatch):
    import face_encoder

    class DummyRecognizer:
        def alignCrop(self, image, face):
            return "aligned"

        def feature(self, image):
            assert image == "aligned"
            return np.array([[1.0, 2.0, 3.0]])

    monkeypatch.setattr(face_encoder, "_get_recognizer", lambda: DummyRecognizer())
    result = face_encoder.encode_face(None, None)
    assert np.array_equal(result, np.array([1.0, 2.0, 3.0]))


def test_face_encoding_cache_roundtrip_in_temp_dir(database_module, monkeypatch, tmp_path):
    import face_encoder
    filename = tmp_path / "only_test_encodings.pkl"
    monkeypatch.setattr(face_encoder, "ENCODINGS_FILE", str(filename))
    monkeypatch.setattr(face_encoder, "_known_encodings", {})
    face_encoder.add_face_encoding("S001", np.array([0.5, 0.1]))
    assert filename.is_file()
    assert face_encoder.get_known_count() == 1
    face_encoder.load_encodings()
    assert face_encoder.get_known_count() == 1
    assert face_encoder.remove_face_encoding("S001") is True
    assert face_encoder.remove_face_encoding("S001") is False
    assert face_encoder.get_known_count() == 0


def test_save_cropped_face_only_writes_test_file(database_module, monkeypatch, tmp_path):
    import face_encoder
    monkeypatch.setattr(face_encoder, "KNOWN_FACES_DIR", str(tmp_path))
    path = face_encoder.save_cropped_face(
        "STUDENT_TEST", np.zeros((120, 120, 3), dtype=np.uint8),
        np.array([40, 40, 20, 20] + [0] * 10),
    )
    assert path == str(tmp_path / "STUDENT_TEST.jpg")
    assert (tmp_path / "STUDENT_TEST.jpg").exists()


def test_load_encodings_when_file_absent(database_module, monkeypatch, tmp_path):
    import face_encoder
    monkeypatch.setattr(face_encoder, "ENCODINGS_FILE", str(tmp_path / "absent.pkl"))
    monkeypatch.setattr(face_encoder, "_known_encodings", {"OLD": np.ones(3)})
    assert face_encoder.load_encodings() == {}
