import json

import httpx2
from fakes import FakeChain
from fastapi.testclient import TestClient

from lazyagent.server import create_app
from lazyagent.tts import DEFAULT_VOICE, MAX_CHARS, MODEL, ElevenLabsTts

ORIGIN = "http://localhost:5174"
AUDIO = b"ID3fake-mp3-bytes" * 100


async def no_claude(tools):
    raise AssertionError("not used")


def upstream(status: int = 200, seen: list | None = None):
    """Stands in for ElevenLabs (no network): records each request and answers `status` with fake mp3 bytes."""

    def handler(req: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(req)
        if status != 200:
            return httpx2.Response(status, json={"detail": "nope"})
        return httpx2.Response(200, content=AUDIO, headers={"content-type": "audio/mpeg"})

    return httpx2.MockTransport(handler)


def client(tts):
    return TestClient(create_app(FakeChain(), no_claude, (ORIGIN,), tts=tts))


def test_streams_audio_from_elevenlabs():
    seen: list = []
    tts = ElevenLabsTts(key=lambda: "sk-test", transport=upstream(seen=seen))
    res = client(tts).post("/tts", json={"text": "  Sent 0.1 ETH to Alice.  "}, headers={"origin": ORIGIN})
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.content == AUDIO
    assert res.headers["access-control-allow-origin"] == ORIGIN
    (req,) = seen
    assert req.url.path == f"/v1/text-to-speech/{DEFAULT_VOICE}/stream"
    assert req.headers["xi-api-key"] == "sk-test"
    assert json.loads(req.content) == {"text": "Sent 0.1 ETH to Alice.", "model_id": MODEL}


def test_voice_is_overridable_and_text_is_capped():
    seen: list = []
    tts = ElevenLabsTts(key=lambda: "sk-test", voice=lambda: "custom-voice", transport=upstream(seen=seen))
    client(tts).post("/tts", json={"text": "a" * (MAX_CHARS + 500)}, headers={"origin": ORIGIN})
    assert seen[0].url.path == "/v1/text-to-speech/custom-voice/stream"
    assert len(json.loads(seen[0].content)["text"]) == MAX_CHARS


def test_rejects_other_origins():
    seen: list = []
    tts = ElevenLabsTts(key=lambda: "sk-test", transport=upstream(seen=seen))
    res = client(tts).post("/tts", json={"text": "hi"}, headers={"origin": "https://evil.example"})
    assert res.status_code == 403
    assert seen == []


def test_clear_error_without_key():
    res = client(ElevenLabsTts(key=lambda: None, transport=upstream())).post("/tts", json={"text": "hi"}, headers={"origin": ORIGIN})
    assert res.status_code == 503
    assert "ELEVENLABS_API_KEY is not set" in res.json()["error"]


def test_upstream_error_is_503_without_leaking_key():
    tts = ElevenLabsTts(key=lambda: "sk-secret", transport=upstream(status=401))
    res = client(tts).post("/tts", json={"text": "hi"}, headers={"origin": ORIGIN})
    assert res.status_code == 503
    assert "401" in res.json()["error"]
    assert "sk-secret" not in res.text


def test_empty_text_is_rejected():
    res = client(ElevenLabsTts(key=lambda: "sk-test", transport=upstream())).post("/tts", json={"text": "   "}, headers={"origin": ORIGIN})
    assert res.status_code == 400


def test_cors_preflight_allows_wallet_origin():
    res = client(None).options(
        "/tts", headers={"origin": ORIGIN, "access-control-request-method": "POST", "access-control-request-headers": "content-type"}
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == ORIGIN
