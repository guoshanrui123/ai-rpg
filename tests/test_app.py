import wave
from unittest.mock import Mock

import pytest

import app as web


@pytest.fixture(autouse=True)
def reset(monkeypatch, tmp_path):
    web.sessions.clear()
    monkeypatch.setattr(web, "chatbot", Mock(stream=lambda message, history: "回复：" + message))
    monkeypatch.setattr(web, "ROOT", tmp_path)
    web.app.config.update(TESTING=True, SECRET_KEY="test-only-session-signing-value")
    for name in ("XFYUN_APP_ID", "XFYUN_API_KEY", "XFYUN_API_SECRET", "OPENAI_API_KEY", "DASHSCOPE_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def post(client, message="你好"):
    client.get("/chatpage?card=1")
    with client.session_transaction() as s:
        token = s["csrf_token"]
    return client.post("/send_message", data={"message": message}, headers={"X-CSRF-Token": token})


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/storycontextpage",
        "/characterselection",
        "/chatpage?card=1",
        "/chatpage?card=2",
        "/chatpage?card=3",
        "/finalend",
    ],
)
def test_pages(path):
    assert web.app.test_client().get(path).status_code == 200


def test_invalid_card_and_host():
    client = web.app.test_client()
    assert client.get("/chatpage?card=9").status_code == 400
    assert client.get("/", base_url="http://attacker.example").status_code == 400


def test_session_isolation_and_text_without_speech():
    first, second = web.app.test_client(), web.app.test_client()
    result = post(first, "私密剧情")
    assert result.status_code == 200
    assert result.json["audio_url"] is None
    assert first.get("/get_messages").json["chat_history"][-1]["content"] == "回复：私密剧情"
    assert second.get("/get_messages").json["chat_history"] == []
    assert result.headers["Cache-Control"] == "no-store"


def test_csrf_and_input_limits():
    client = web.app.test_client()
    assert client.post("/send_message", data={"message": "hello"}).status_code == 403
    assert post(client, "   ").status_code == 400
    assert post(client, "x" * 4001).status_code == 400
    assert post(client, "x" * 40000).status_code == 413


def test_upstream_exception_is_redacted(monkeypatch):
    monkeypatch.setattr(web, "chatbot", Mock(stream=Mock(side_effect=RuntimeError("private-upstream-value"))))
    result = post(web.app.test_client())
    assert result.status_code == 502
    assert b"private-upstream-value" not in result.data


def test_missing_credentials(monkeypatch):
    monkeypatch.setattr(web, "chatbot", None)
    assert post(web.app.test_client()).status_code == 503


@pytest.mark.parametrize("roll,passed", [(1, True), (79, True), (80, False), (100, False)])
def test_roll_boundary(monkeypatch, roll, passed):
    monkeypatch.setattr(web.secrets, "randbelow", lambda upper: roll - 1)
    result = web.apply_attribute_check("生成关于力量的随机数", "1")
    assert ("恭喜" in result) == passed


def test_card_attributes(monkeypatch):
    monkeypatch.setattr(web.secrets, "randbelow", lambda upper: 49)
    assert "恭喜" in web.apply_attribute_check("生成关于力量的随机数", "1")
    assert "并未" in web.apply_attribute_check("生成关于力量的随机数", "3")


def test_speech_failure_keeps_answer(monkeypatch):
    for name in ("XFYUN_APP_ID", "XFYUN_API_KEY", "XFYUN_API_SECRET"):
        monkeypatch.setenv(name, "test-placeholder")
    monkeypatch.setattr(web, "synthesize", Mock(side_effect=RuntimeError("private-speech-error")))
    result = post(web.app.test_client())
    assert result.status_code == 200
    assert result.json["answer"] and result.json["audio_url"] is None
    assert b"private-speech-error" not in result.data


def test_audio_access_requires_owner(tmp_path):
    owner, other = web.app.test_client(), web.app.test_client()
    owner.get("/chatpage")
    with owner.session_transaction() as s:
        sid = s["player_id"]
    directory = tmp_path / "runtime/audio" / sid
    directory.mkdir(parents=True)
    (directory / "sample.wav").write_bytes(b"RIFF-test")
    assert owner.get("/audio/sample.wav").status_code == 200
    assert other.get("/audio/sample.wav").status_code == 404
    assert owner.get("/audio/../sample.wav").status_code == 404


def test_session_expiry(monkeypatch):
    client = web.app.test_client()
    post(client)
    for player in web.sessions.values():
        player["last_seen"] -= web.SESSION_TTL + 1
    assert client.get("/get_messages").json["chat_history"] == []


def test_pcm_conversion(tmp_path):
    from keda import pcm2wav

    pcm = tmp_path / "sample.pcm"
    wav = tmp_path / "sample.wav"
    pcm.write_bytes(b"\x00\x00" * 160)
    assert pcm2wav(pcm, wav)
    with wave.open(str(wav)) as audio:
        assert audio.getnframes() == 160
        assert audio.getframerate() == 16000
    pcm.write_bytes(b"")
    with pytest.raises(ValueError):
        pcm2wav(pcm, wav)
