import { describe, it, expect, vi, afterEach } from "vitest";
import { ClipReader } from "./ClipReader";
import { SampleIndex } from "./SampleIndex";
import type { MediaSource } from "./MediaSource";
import type { SampleMeta } from "./sample-types";

/**
 * Regression test for the 60fps-export deadlock.
 *
 * The decode ring holds 8 frames; the export-exact fetch keeps a 200ms history
 * window (TRIM_BEHIND_US). For sources above ~40fps the whole full ring fits
 * inside that window (200ms × 60fps = 12 > 8), so the time-based trim can't free
 * a slot. When frameAtExact must decode MORE than the ring capacity to reach the
 * target (e.g. a seek landing well past a keyframe, or the decoder briefly
 * lagging), the ring fills with behind-target frames the window won't evict, the
 * pump deadlocks on awaitSpace(), and frameAtExact crawls to its 3000ms budget
 * returning a stale frame (~0.5fps export). The dropOldest fix must keep forward
 * progress so each exact frame resolves promptly.
 */

/** Fake VideoFrame — the engine only touches timestamp / close / clone. */
function makeFrame(timestamp: number): VideoFrame & { _closed: boolean } {
  const f = {
    timestamp,
    _closed: false,
    close(this: { _closed: boolean }): void {
      this._closed = true;
    },
    clone(): VideoFrame {
      return makeFrame(timestamp);
    },
  };
  return f as unknown as VideoFrame & { _closed: boolean };
}

class FakeEncodedVideoChunk {
  readonly timestamp: number;
  constructor(init: { timestamp: number }) {
    this.timestamp = init.timestamp;
  }
}

/**
 * Minimal VideoDecoder: emits one frame per chunk, in order, with
 * timestamp == chunk.cts, SYNCHRONOUSLY. Real decoders emit asynchronously
 * after B-frame reorder, but the deadlock under test lives in the ring's trim
 * policy and is independent of decode latency — synchronous emit keeps the test
 * deterministic while still exercising the pump's hasSpace/awaitSpace pacing.
 */
class FakeVideoDecoder {
  state = "unconfigured";
  decodeQueueSize = 0;
  private readonly emit: (f: VideoFrame) => void;
  constructor(init: { output: (f: VideoFrame) => void; error: (e: unknown) => void }) {
    this.emit = init.output;
  }
  configure(): void {
    this.state = "configured";
  }
  decode(chunk: { timestamp: number }): void {
    this.emit(makeFrame(chunk.timestamp));
  }
  flush(): Promise<void> {
    return Promise.resolve();
  }
  close(): void {
    this.state = "closed";
  }
}

/**
 * Build a fake MediaSource of `n` frames at the given fps (constant spacing).
 * `keyframeEvery` controls keyframe density — large values force seeks to land
 * far past a keyframe, the worst case for the trim-window deadlock.
 */
function fakeSource(fps: number, n: number, keyframeEvery: number): MediaSource {
  const spacing = Math.round(1_000_000 / fps);
  const samples: SampleMeta[] = Array.from({ length: n }, (_, i) => ({
    data: new Uint8Array(0),
    cts_us: i * spacing,
    dts_us: i * spacing,
    duration_us: spacing,
    is_sync: i % keyframeEvery === 0,
  }));
  return {
    samples,
    index: new SampleIndex(samples),
    config: { codec: "av01", codedWidth: 1920, codedHeight: 1080 } as VideoDecoderConfig,
    width: 1920,
    height: 1080,
    codec: "av01",
    durationUs: n * spacing,
    audio: null,
    hasAudio: false,
  } as unknown as MediaSource;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ClipReader.frameAtExact — high-fps export", () => {
  it("resolves an EXACT 60fps frame seeked far past its keyframe", async () => {
    // The deadlock trigger: keyframe at 0, target = frame 30. Reaching it needs
    // decoding 30 frames through the 8-slot ring; at 60fps the 200ms window can
    // never trim the full ring, so without dropOldest the pump deadlocks and
    // frameAtExact returns frame ~18 (stale) after burning its 3s budget.
    vi.stubGlobal("VideoDecoder", FakeVideoDecoder);
    vi.stubGlobal("EncodedVideoChunk", FakeEncodedVideoChunk);

    const fps = 60;
    const spacing = Math.round(1_000_000 / fps);
    const reader = new ClipReader(fakeSource(fps, 120, /* keyframeEvery */ 120));

    const start = performance.now();
    const target = 30 * spacing;
    const frame = await reader.frameAtExact(target);
    expect(frame).not.toBeNull();
    expect(frame!.timestamp).toBe(target);
    frame!.close();
    // A regression would spend ~3s in the budget loop (and likely trip the test
    // timeout); the fix resolves in milliseconds.
    expect(performance.now() - start).toBeLessThan(2000);

    reader.dispose();
  });

  it("walks a 60fps source frame-by-frame returning each EXACT target", async () => {
    vi.stubGlobal("VideoDecoder", FakeVideoDecoder);
    vi.stubGlobal("EncodedVideoChunk", FakeEncodedVideoChunk);

    const fps = 60;
    const spacing = Math.round(1_000_000 / fps);
    const reader = new ClipReader(fakeSource(fps, 60, /* keyframeEvery */ 12));

    const start = performance.now();
    for (let k = 0; k <= 24; k++) {
      const target = k * spacing;
      const frame = await reader.frameAtExact(target);
      expect(frame!.timestamp, `frame #${k} must be the EXACT target`).toBe(target);
      frame!.close();
    }
    expect(performance.now() - start).toBeLessThan(2000);

    reader.dispose();
  });

  it("still works for a 30fps source (below the saturation threshold)", async () => {
    vi.stubGlobal("VideoDecoder", FakeVideoDecoder);
    vi.stubGlobal("EncodedVideoChunk", FakeEncodedVideoChunk);

    const fps = 30;
    const spacing = Math.round(1_000_000 / fps);
    const reader = new ClipReader(fakeSource(fps, 40, /* keyframeEvery */ 12));

    for (let k = 0; k <= 20; k++) {
      const target = k * spacing;
      const frame = await reader.frameAtExact(target);
      expect(frame!.timestamp).toBe(target);
      frame!.close();
    }
    reader.dispose();
  });
});

/**
 * Regression test for the news_desk VP9 "picture walks forward then snaps
 * back" bug (task.md 续 — reproduced live against the real downloaded file
 * outside the app: real decode measured at ~18x realtime, yet playback
 * visibly oscillated because `needsRepositionFor` reseeked back to the SAME
 * keyframe on nearly every call).
 *
 * The trigger: once a fast-moving real-time target outruns the buffer
 * (`mediaTime > latest + FORWARD_LOOKAHEAD_US`) or falls behind it
 * (`mediaTime < earliest`), the OLD code unconditionally reseeked — even
 * when the target was still inside the GOP already being decoded. That
 * discarded the pump's progress and restarted from the identical keyframe,
 * so a lagging-but-progressing pump never got an uninterrupted run to catch
 * up: every call re-triggered the same discard-and-restart, which reads on
 * screen as the picture perpetually snapping back toward the GOP's start.
 */
describe("ClipReader — same-GOP reposition livelock", () => {
  it("does not reseek when the target is still within the currently-decoding GOP", () => {
    vi.stubGlobal("VideoDecoder", FakeVideoDecoder);
    vi.stubGlobal("EncodedVideoChunk", FakeEncodedVideoChunk);

    // One keyframe at index 0, the next at index 200 — a single big GOP
    // spanning the whole probed range, matching the real VP9 file's ~5.3s GOPs.
    const reader = new ClipReader(fakeSource(30, 400, /* keyframeEvery */ 200)) as unknown as {
      seek: { cursor: number; keyIdx: number; targetMediaUs: number } | null;
      pumpRunning: boolean;
      buffer: { push: (f: VideoFrame) => void };
      needsRepositionFor: (mediaTime: number) => boolean;
      dispose: () => void;
    };

    // An active seek into the first GOP, buffer holding only early frames —
    // the exact shape of a pump that's lagging a fast-moving real-time target.
    reader.seek = { cursor: 5, keyIdx: 0, targetMediaUs: 0 };
    reader.pumpRunning = true;
    reader.buffer.push(makeFrame(100_000));
    reader.buffer.push(makeFrame(133_000));

    // Target is >1s (FORWARD_LOOKAHEAD_US) past the buffer's latest frame but
    // still inside the SAME GOP (next keyframe is index 200, far later) — must
    // NOT reseek; the pump is already positioned correctly and just needs to
    // keep running.
    expect(reader.needsRepositionFor(5_000_000)).toBe(false);

    // A target that has actually moved into the NEXT GOP must still trigger a
    // real reseek (regression guard the other direction).
    const nextGopUs = Math.round((200 * 1_000_000) / 30);
    expect(reader.needsRepositionFor(nextGopUs)).toBe(true);

    reader.dispose();
  });

  it("end-to-end: a real-time target racing far ahead within one GOP never returns a backward-jumping frame", async () => {
    vi.stubGlobal("VideoDecoder", FakeVideoDecoder);
    vi.stubGlobal("EncodedVideoChunk", FakeEncodedVideoChunk);

    const fps = 30;
    const n = 400;
    // Single GOP for the whole test range.
    const reader = new ClipReader(fakeSource(fps, n, /* keyframeEvery */ n + 1));

    const timestamps: number[] = [];
    let target = 0;
    for (let i = 0; i < 10; i++) {
      const frame = await reader.frameAt(target);
      if (frame) {
        timestamps.push(frame.timestamp);
        frame.close();
      }
      // Each jump is well past FORWARD_LOOKAHEAD_US (1s) — the livelock
      // trigger — but still inside this single-GOP source.
      target += 2_000_000;
    }

    for (let i = 1; i < timestamps.length; i++) {
      expect(timestamps[i]!, `frame #${i} must not regress behind #${i - 1}`).toBeGreaterThanOrEqual(
        timestamps[i - 1]!,
      );
    }

    reader.dispose();
  });
});
