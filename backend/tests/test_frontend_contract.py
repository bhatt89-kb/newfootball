from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"

def test_frontend_assets_are_split():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'href="styles.css"' in html
    assert 'src="app.js"' in html
    assert "<style>" not in html

def test_frontend_calls_versioned_chat_api():
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    assert "newfootball-1.onrender.com/api/v1" in js
    assert "callApi('/chat'" in js
    assert "FETCH_TIMEOUT_MS = 15000" in js
