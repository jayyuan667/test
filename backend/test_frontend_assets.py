from pathlib import Path

import backend.app as app_module
from backend.app import app


def test_vite_public_assets_are_served_from_dist_root():
    dist_dir = Path(__file__).resolve().parent.parent / "frontend-react" / "dist"
    assert (dist_dir / "dica-logo.png").is_file()
    assert (dist_dir / "favicon-32.png").is_file()
    assert (dist_dir / "favicon.png").is_file()
    assert (dist_dir / "apple-touch-icon.png").is_file()

    client = app.test_client()

    logo_response = client.get("/dica-logo.png")
    assert logo_response.status_code == 200
    assert logo_response.mimetype == "image/png"

    favicon_response = client.get("/favicon.png")
    assert favicon_response.status_code == 200
    assert favicon_response.mimetype == "image/png"

    favicon_32_response = client.get("/favicon-32.png")
    assert favicon_32_response.status_code == 200
    assert favicon_32_response.mimetype == "image/png"

    apple_touch_response = client.get("/apple-touch-icon.png")
    assert apple_touch_response.status_code == 200
    assert apple_touch_response.mimetype == "image/png"


def test_cors_origins_can_be_configured_from_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://gongyi.neusym.cn, http://127.0.0.1:5192")

    assert app_module._get_cors_origins() == [
        "https://gongyi.neusym.cn",
        "http://127.0.0.1:5192",
    ]
