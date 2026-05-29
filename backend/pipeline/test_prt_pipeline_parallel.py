import os
from unittest.mock import patch
import pytest


def _make_artifacts_stub(prt_path, output_dir):
    """Run prepare_prt_artifacts with all external I/O mocked out."""
    with patch("backend.prt_pipeline.run_conversion") as mock_conv, \
         patch("backend.prt_pipeline.capture_three_views"), \
         patch("backend.prt_pipeline.capture_creo_views") as mock_creo, \
         patch("backend.prt_pipeline.read_creo_zhushi", return_value="注释内容"), \
         patch("backend.prt_pipeline.analyze_step_geometry",
               return_value={"shape_class": "板类", "dimensions": {"x": 100, "y": 50, "z": 30}}):

        def fake_conversion(prt, zip_out, step_out):
            open(step_out, "w").close()
        mock_conv.side_effect = fake_conversion

        mock_creo.return_value = (True, str(output_dir) + "/creo_views", str(output_dir) + "/creo_views/zhushi.txt")

        for name in ("front", "right", "top"):
            open(os.path.join(output_dir, f"{name}.png"), "w").close()

        from backend.prt_pipeline import prepare_prt_artifacts
        return prepare_prt_artifacts(prt_path, output_dir)


def test_prepare_prt_artifacts_returns_geo_data(tmp_path):
    prt = tmp_path / "part.prt"
    prt.write_text("dummy")
    result = _make_artifacts_stub(str(prt), str(tmp_path))
    assert "geo_data" in result
    assert result["geo_data"] is not None


def test_prepare_prt_artifacts_geo_data_none_when_analysis_fails(tmp_path):
    prt = tmp_path / "part.prt"
    prt.write_text("dummy")
    with patch("backend.prt_pipeline.analyze_step_geometry", side_effect=RuntimeError("no freecad")):
        with patch("backend.prt_pipeline.run_conversion") as mock_conv, \
             patch("backend.prt_pipeline.capture_three_views"), \
             patch("backend.prt_pipeline.capture_creo_views",
                   return_value=(False, str(tmp_path / "creo_views"), "")), \
             patch("backend.prt_pipeline.read_creo_zhushi", return_value=""):
            def fake_conv(prt, zip_out, step_out):
                open(step_out, "w").close()
            mock_conv.side_effect = fake_conv
            from backend.prt_pipeline import prepare_prt_artifacts
            result = prepare_prt_artifacts(str(prt), str(tmp_path))
    assert result["geo_data"] is None


def test_prepare_prt_artifacts_both_threads_called(tmp_path):
    prt = tmp_path / "part.prt"
    prt.write_text("dummy")
    call_log = []

    def fake_conv(prt, zip_out, step_out):
        call_log.append("conversion")
        open(step_out, "w").close()

    def fake_creo(prt_path, output_dir):
        call_log.append("creo")
        return (False, str(tmp_path / "creo_views"), "")

    with patch("backend.prt_pipeline.run_conversion", side_effect=fake_conv), \
         patch("backend.prt_pipeline.capture_three_views"), \
         patch("backend.prt_pipeline.capture_creo_views", side_effect=fake_creo), \
         patch("backend.prt_pipeline.read_creo_zhushi", return_value=""), \
         patch("backend.prt_pipeline.analyze_step_geometry",
               return_value={"shape_class": "一般件", "dimensions": {}}):
        from backend.prt_pipeline import prepare_prt_artifacts
        prepare_prt_artifacts(str(prt), str(tmp_path))

    assert "conversion" in call_log
    assert "creo" in call_log
