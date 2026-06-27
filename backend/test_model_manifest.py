import hashlib
import json

from backend.services.model_manifest import load_model_manifest, verify_model_file


def test_model_manifest_verifies_sha256(tmp_path):
    model = tmp_path / "best.onnx"
    model.write_bytes(b"model-bytes")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    manifest_path = tmp_path / "model-manifest.json"
    manifest_path.write_text(
        json.dumps({
            "name": "drawing-yolo",
            "version": "1.0.0",
            "format": "onnx",
            "sha256": digest,
            "classes": [
                "code_hole",
                "through_hole",
                "blind_hole",
                "threaded_hole",
                "chamfer",
                "counterbore",
                "countersink",
            ],
            "input_size": 1280,
            "confidence_threshold": 0.25,
            "released_at": "2026-06-20",
        }),
        encoding="utf-8",
    )
    manifest = load_model_manifest(manifest_path)
    assert verify_model_file(model, manifest) == (True, "")


def test_model_manifest_rejects_hash_mismatch(tmp_path):
    model = tmp_path / "best.onnx"
    model.write_bytes(b"wrong")
    ok, reason = verify_model_file(model, {"sha256": "0" * 64})
    assert ok is False
    assert "SHA-256" in reason
