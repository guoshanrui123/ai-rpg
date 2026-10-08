import base64
import json
import wave
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest

import keda


def test_signed_host_matches_url():
    url = keda.Ws_Param("test-app", "test-key", "test-secret", "你好").create_url()
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert query["host"][0] == parsed.hostname == "tts-api.xfyun.cn"
    assert "test-secret" not in url


def install_socket(monkeypatch, payload):
    def factory(url, **callbacks):
        ws = Mock()

        def run(**kwargs):
            assert "sslopt" not in kwargs
            callbacks["on_open"](ws)
            callbacks["on_message"](ws, json.dumps(payload))

        ws.run_forever.side_effect = run
        return ws

    monkeypatch.setattr(keda.websocket, "WebSocketApp", factory)


def test_last_frame_written_and_names_unique(monkeypatch, tmp_path):
    install_socket(monkeypatch, {"code": 0, "data": {"audio": base64.b64encode(b"\0\0" * 8).decode(), "status": 2}})
    first = keda.synthesize("你好", tmp_path, "test-app", "test-key", "test-secret")
    second = keda.synthesize("你好", tmp_path, "test-app", "test-key", "test-secret")
    assert first != second
    with wave.open(str(tmp_path / first)) as audio:
        assert audio.getnframes() == 8


@pytest.mark.parametrize(
    "payload",
    [
        {"code": 100, "message": "error without data"},
        {"code": 0, "data": {"audio": "", "status": 2}},
        {"code": 0, "data": {"audio": "bad base64", "status": 2}},
        {"code": 0, "data": {"audio": "AAA=", "status": 1}},
    ],
)
def test_failed_or_incomplete_stream_rejected(monkeypatch, tmp_path, payload):
    install_socket(monkeypatch, payload)
    with pytest.raises(RuntimeError):
        keda.synthesize("你好", tmp_path, "test-app", "test-key", "test-secret")
    assert not list(tmp_path.glob("*.wav"))
