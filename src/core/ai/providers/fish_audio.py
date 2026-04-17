"""Fish Audio TTS provider.

Wraps fish_audio_sdk.Session.tts() streaming — writes audio chunks to
`output_path` as they arrive. Cooperative cancellation via a caller-
supplied `should_cancel()` callable (Phase 7 will integrate with
CancellationToken directly).

Phase 1: extracted from tools/text2video/text2video.py. Phase 7 will map
fish_audio_sdk exceptions onto AIError.Kind.
"""

from typing import Callable


def is_sdk_available() -> bool:
    """True if fish_audio_sdk is importable. UI layer uses this to grey out
    the TTS tool / show an install hint when the SDK isn't installed."""
    try:
        import fish_audio_sdk  # noqa: F401
        return True
    except ImportError:
        return False


def synthesize(
    text: str,
    output_path: str,
    *,
    api_key: str,
    voice_id: str,
    audio_format: str = "mp3",
    should_cancel: Callable[[], bool] | None = None,
    on_chunk: Callable[[int], None] | None = None,
) -> None:
    """Stream TTS audio to `output_path`.

    Args:
        text:          Input text.
        output_path:   Destination file (overwritten if exists).
        api_key:       Fish Audio API key.
        voice_id:      reference_id (fish.audio model ID).
        audio_format:  'mp3' | 'wav' | 'opus'.
        should_cancel: Optional predicate; when it returns True we raise
                       InterruptedError mid-stream. Feature layer wraps
                       this around its own stop flag.
        on_chunk:      Optional callback(total_bytes_written_so_far) for
                       progress reporting. Called after each chunk.

    Raises:
        RuntimeError:    SDK not installed or API call failed.
        InterruptedError: should_cancel() returned True.
    """
    try:
        from fish_audio_sdk import Session, TTSRequest
    except ImportError as e:
        raise RuntimeError(
            "fish_audio_sdk not installed; pip install fish_audio_sdk"
        ) from e

    # SDK 1.3.x: Session.tts() directly returns Generator[bytes]; no context
    # manager and no .iter_bytes() on the return value. Older code (pre-M5)
    # used a stale `with ... as resp: resp.iter_bytes()` pattern that never
    # worked against this SDK version.
    session = Session(api_key)
    total = 0
    try:
        with open(output_path, "wb") as f:
            for chunk in session.tts(TTSRequest(
                reference_id=voice_id, text=text, format=audio_format,
            )):
                if should_cancel and should_cancel():
                    raise InterruptedError("TTS cancelled")
                f.write(chunk)
                total += len(chunk)
                if on_chunk:
                    on_chunk(total)
    except InterruptedError:
        raise
    except Exception as e:
        msg = str(e)
        if hasattr(e, "message"):
            msg = e.message
        raise RuntimeError(
            f"Fish Audio TTS error: {msg} "
            f"(voice_id={voice_id!r}, text_len={len(text)})"
        ) from e
