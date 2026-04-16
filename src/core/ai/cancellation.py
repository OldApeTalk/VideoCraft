"""Cooperative cancellation token.

Python has no safe thread-interrupt primitive, so cancellation has to be
cooperative: workers check the token at safe points and abort themselves.

Phase 1 scaffolds the contract; Phase 7 wires provider adapters to
`register_abort(lambda: response.close())` so HTTP requests can be torn
down mid-flight (<1s cancel latency). Without that, cancellation waits for
the current call to finish naturally.

Three-layer usage:
  - UI: on cancel button click, call token.cancel() — returns immediately.
  - Feature: between chunks, call token.throw_if_cancelled(provider).
  - Provider adapter: at HTTP start, token.register_abort(abort_fn).
"""

from typing import Callable
from core.ai.errors import AIError, Kind


class CancellationToken:
    def __init__(self):
        self._cancelled: bool = False
        self._abort_cbs: list[Callable[[], None]] = []

    def cancel(self) -> None:
        """Mark cancelled and fire all registered abort callbacks."""
        self._cancelled = True
        for cb in self._abort_cbs:
            try:
                cb()
            except Exception:
                # Abort callbacks must not raise — swallow to guarantee
                # the other callbacks still run.
                pass
        self._abort_cbs.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def throw_if_cancelled(self, provider: str = "") -> None:
        """Raise AIError(Kind.CANCELLED) if cancel was called.

        Feature layer should call this at chunk boundaries to bail early.
        """
        if self._cancelled:
            raise AIError(Kind.CANCELLED, provider or "—", "Cancelled by user")

    def register_abort(self, cb: Callable[[], None]) -> None:
        """Register a callback that aborts the provider's in-flight request.

        If already cancelled when called, invokes cb() immediately so that
        a provider starting a request *after* cancel still tears down.
        """
        if self._cancelled:
            try:
                cb()
            except Exception:
                pass
        else:
            self._abort_cbs.append(cb)
