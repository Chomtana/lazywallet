"""Spoken replies: ElevenLabs streaming text-to-speech, proxied by the agent's POST /tts.

The API key (ELEVENLABS_API_KEY in the root .env, loaded by config.load_settings) is only read here, in the agent,
and only ever sent in the xi-api-key header — never to the browser, a URL, a log line or an error message."""

import os
from collections.abc import AsyncIterator, Callable
from typing import Protocol

import httpx2

ELEVENLABS_API = "https://api.elevenlabs.io/v1"
KEY_ENV = "ELEVENLABS_API_KEY"
VOICE_ENV = "ELEVENLABS_VOICE_ID"
DEFAULT_VOICE = "cgSgspJ2msm6clMCkdW9"  # "Jessica" (premade): warm, bright young female voice
MODEL = "eleven_flash_v2_5"  # lowest-latency model (~75 ms)
OUTPUT_FORMAT = "mp3_44100_128"
MAX_CHARS = 2000  # replies are short; caps cost if something sends a novel


class TtsUnavailable(Exception):
    """No key configured, or ElevenLabs refused the request."""


class Tts(Protocol):
    async def stream(self, text: str) -> AsyncIterator[bytes]: ...


class ElevenLabsTts:
    def __init__(
        self,
        base: str = ELEVENLABS_API,
        key: Callable[[], str | None] = lambda: os.environ.get(KEY_ENV),
        voice: Callable[[], str] = lambda: os.environ.get(VOICE_ENV) or DEFAULT_VOICE,
        transport: httpx2.AsyncBaseTransport | None = None,
    ):
        self.base, self.key, self.voice, self.transport = base, key, voice, transport

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        """Opens the upstream stream (raising TtsUnavailable before any audio is sent) and returns its chunks."""
        key = self.key()
        if not key:
            raise TtsUnavailable(f"{KEY_ENV} is not set")
        client = httpx2.AsyncClient(timeout=30, transport=self.transport)
        req = client.build_request(
            "POST",
            f"{self.base}/text-to-speech/{self.voice()}/stream",
            params={"output_format": OUTPUT_FORMAT},
            headers={"xi-api-key": key, "accept": "audio/mpeg"},
            json={"text": text, "model_id": MODEL},
        )
        try:
            res = await client.send(req, stream=True)
        except httpx2.HTTPError as e:
            await client.aclose()
            raise TtsUnavailable("ElevenLabs is unreachable") from e
        if res.status_code != 200:
            await res.aclose()
            await client.aclose()
            raise TtsUnavailable(f"ElevenLabs answered {res.status_code}")

        async def chunks() -> AsyncIterator[bytes]:
            try:
                async for chunk in res.aiter_bytes():
                    yield chunk
            finally:
                await res.aclose()
                await client.aclose()

        return chunks()
