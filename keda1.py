"""Compatibility entry point for the former duplicate speech demo."""

import os
from pathlib import Path

from dotenv import load_dotenv

from keda import Ws_Param, pcm2wav, synthesize  # noqa: F401

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    names = ("XFYUN_APP_ID", "XFYUN_API_KEY", "XFYUN_API_SECRET")
    if not all(os.getenv(name) for name in names):
        raise SystemExit("请先在 .env 配置讯飞语音凭据。")
    filename = synthesize(
        "欢迎来到 AI 跑团。", root / "runtime" / "audio" / "demo", *(os.environ[name] for name in names)
    )
    print(f"已生成音频：runtime/audio/demo/{filename}")
