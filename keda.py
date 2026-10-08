"""XFYun speech synthesis with verified TLS and per-request output files."""

import base64
import hashlib
import hmac
import json
import threading
import time
import uuid
import wave
from pathlib import Path
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import websocket


class Ws_Param:
    def __init__(self, APPID, APIKey, APISecret, Text):
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.CommonArgs = {"app_id": APPID}
        self.BusinessArgs = {"aue": "raw", "auf": "audio/L16;rate=16000", "vcn": "xiaoyan", "tte": "utf8"}
        self.Data = {"status": 2, "text": base64.b64encode(Text.encode("utf-8")).decode("ascii")}

    def create_url(self):
        host = "tts-api.xfyun.cn"
        date = format_date_time(time.time())
        origin = f"host: {host}\ndate: {date}\nGET /v2/tts HTTP/1.1"
        signature = base64.b64encode(
            hmac.new(self.APISecret.encode(), origin.encode(), hashlib.sha256).digest()
        ).decode()
        authorization = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
        return f"wss://{host}/v2/tts?" + urlencode(
            {
                "authorization": base64.b64encode(authorization.encode()).decode(),
                "date": date,
                "host": host,
            }
        )


def pcm2wav(pcm_file, wav_file, channels=1, bits=16, sample_rate=16000):
    data = Path(pcm_file).read_bytes()
    if not data or len(data) % (channels * (bits // 8)):
        raise ValueError("Invalid PCM payload")
    Path(wav_file).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_file), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(bits // 8)
        output.setframerate(sample_rate)
        output.writeframes(data)
    return True


def synthesize(text, output_dir, app_id, api_key, api_secret, timeout=30):
    params = Ws_Param(app_id, api_key, api_secret, text)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Bound retained audio in each session; generated files are never published.
    for old_file in output_dir.glob("*.wav"):
        if old_file.stat().st_mtime < time.time() - 3600:
            old_file.unlink(missing_ok=True)
    audio = bytearray()
    complete = False
    failed = False

    def on_open(ws):
        ws.send(json.dumps({"common": params.CommonArgs, "business": params.BusinessArgs, "data": params.Data}))

    def on_message(ws, raw):
        nonlocal complete, failed
        try:
            payload = json.loads(raw)
            if payload.get("code") != 0:
                raise ValueError("Speech provider rejected request")
            audio.extend(base64.b64decode(payload["data"]["audio"], validate=True))
            if len(audio) > 16 * 1024 * 1024:
                raise ValueError("Audio payload too large")
            if payload["data"]["status"] == 2:
                complete = True
                ws.close()
        except Exception:
            failed = True
            ws.close()

    def on_error(ws, error):
        nonlocal failed
        failed = True

    def expire():
        nonlocal failed
        failed = True
        ws.close()

    ws = websocket.WebSocketApp(params.create_url(), on_open=on_open, on_message=on_message, on_error=on_error)
    # Socket timeout covers stalled handshakes; timer bounds an established stream.
    websocket.setdefaulttimeout(timeout)
    timer = threading.Timer(timeout, expire)
    timer.daemon = True
    timer.start()
    try:
        ws.run_forever(ping_interval=10, ping_timeout=5)
    finally:
        timer.cancel()
        ws.close()
    if failed or not complete or not audio or len(audio) % 2:
        raise RuntimeError("Speech synthesis did not complete")
    filename = f"{uuid.uuid4().hex}.wav"
    with wave.open(str(output_dir / filename), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(audio)
    return filename
