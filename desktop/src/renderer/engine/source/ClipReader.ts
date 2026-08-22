/**
 * Real-time video clip reader (ported from Phase).
 *
 * Implements VideoSource for one media clip with optional in/out trim. Owns:
 *   - a long-lived VideoDecoder (created on first frameAt, kept alive across
 *     the session — the perf fix vs. "fresh decoder per call" which is O(N²)
 *     inside a GOP)
 *   - a FrameRingBuffer of decoded VideoFrames
 *   - an async pump feeding encoded samples to the decoder, back-pressured on
 *     buffer capacity
 *
 * Time domains:
 *   - frameAt(clipTimeUs): caller coords, [0, durationUs] where
 *     durationUs = sourceOut - sourceIn.
 *   - internally MEDIA coords (cts_us); mediaTime = sourceInUs + clipTime.
 *
 * Seek vs. play:
 *   - forward play within buffered range = no seek, just pickAt. Fast.
 *   - out-of-range target = seek: stop pump, dispose decoder, clear buffer,
 *     cursor to keyframe at-or-before target, start new pump.
 */

import { EngineError } from "../errors";
import type { TimeUs, VideoSource } from "../types";
import { FrameRingBuffer } from "./FrameRingBuffer";
import { MediaSource } from "./MediaSource";

/**
 * Zero-delay yield that stays fast while the window is occluded/unfocused.
 * setTimeout(fn, 0) is subject to Chromium's background timer throttling
 * (clamped to ~1/s, worse after minutes hidden) once the renderer isn't the
 * foreground window — runPump()'s per-sample yield hit exactly that, starving
 * decode and pausing export whenever the app wasn't on top (a3669ff tried
 * disabling backgroundThrottling globally to fix this, but that broke the
 * rAF-driven GPU preview instead — see acf066a / main.ts). postMessage tasks
 * aren't covered by that intervention, so this bypasses it without touching
 * webPreferences.
 */
const yieldQueue: Array<() => void> = [];
const yieldChannel = new MessageChannel();
yieldChannel.port1.onmessage = () => yieldQueue.shift()?.();
function yieldToEventLoop(): Promise<void> {
  return new Promise((resolve) => {
    yieldQueue.push(resolve);
    yieldChannel.port2.postMessage(null);
  });
}

/**
 * Default ring/in-flight capacity — small enough to bound how many decoded
 * VideoFrames (GPU surfaces) preview keeps pinned at once. Export passes a
 * much larger EXPORT_RING_CAPACITY: measured directly (real file, real
 * pipeline, freezedetect-verified) that once an encoder shares the main
 * thread with decode, decoder output arrives in irregular bursts spanning up
 * to ~1.5s instead of a steady ~1-frame-apart cadence — a small ring can hold
 * only a sliver of a burst, silently drops the rest in the output callback,
 * and frameAtExact() then settles for whatever stale frame survived. Export
 * isn't real-time and doesn't need to bound GPU-surface pinning as tightly,
 * so a ring big enough to hold a full burst fixes it directly.
 */
const DEFAULT_RING_CAPACITY = 8;
/** Ring/in-flight capacity for export's frameAtExact() — see DEFAULT_RING_CAPACITY. */
export const EXPORT_RING_CAPACITY = 64;
/** How far past the buffer's latest frame still counts as in-range before a seek. */
const FORWARD_LOOKAHEAD_US = 1_000_000; // 1s
/** Soft trim threshold: drop frames more than this far behind current target. */
const TRIM_BEHIND_US = 200_000; // 200ms
/** Max wait inside frameAt() for the pump to produce a usable frame. */
const FRAME_WAIT_BUDGET_MS = 150;
/** Max time for decoder.flush() before we give up on a seek. */
const FLUSH_TIMEOUT_MS = 2000;
/** Max wait inside frameAtExact() for the pump to reach the target frame. */
const EXACT_WAIT_BUDGET_MS = 3000;

interface SeekState {
  /** Sample index (decode order) the pump should feed next. */
  cursor: number;
  /** Sample index of the current keyframe so the first chunk is typed 'key'. */
  keyIdx: number;
  /** Target media time the seek was scheduled for (diagnostics). */
  targetMediaUs: TimeUs;
}

export class ClipReader implements VideoSource {
  readonly width: number;
  readonly height: number;
  readonly durationUs: TimeUs;

  private readonly mediaSource: MediaSource;
  private readonly sourceInUs: TimeUs;
  private readonly sourceOutUs: TimeUs;

  private readonly ringCapacity: number;
  private decoder: VideoDecoder | null = null;
  private decoderError: Error | null = null;
  private buffer: FrameRingBuffer;

  private seek: SeekState | null = null;
  private pumpRunning = false;
  /** Bumped on every seek; the pump samples this to know when to bail. */
  private generation = 0;

  /**
   * Count of decode() calls submitted to the decoder but not yet resolved via
   * its output callback. decoder.decode() is asynchronous — output arrives
   * later, on the decoder's own schedule — so buffer.hasSpace() (which only
   * reflects frames ALREADY decoded and buffered) can't backpressure the
   * pump: it stays "true" for every sample submitted before the first output
   * arrives, letting the pump race arbitrarily far ahead. Once outputs do
   * arrive in a burst, everything past the ring's capacity gets silently
   * dropped in the output callback — with no in-flight tracking, the reader
   * ends up with only the ring's-worth of frames per GOP and nothing else,
   * which read as a "stuck" picture/stutter once the reposition livelock fix
   * let the pump actually run long enough to hit it. Gating on in-flight
   * count (submitted, not yet resolved) instead keeps outstanding decodes
   * bounded to what the ring can actually hold, so nothing gets dropped.
   */
  private inFlight = 0;
  private inFlightWaiters: Array<() => void> = [];

  private frameAvailableSubs = new Set<() => void>();
  private disposed = false;

  constructor(
    mediaSource: MediaSource,
    sourceInUs?: TimeUs,
    sourceOutUs?: TimeUs,
    ringCapacity: number = DEFAULT_RING_CAPACITY,
  ) {
    this.mediaSource = mediaSource;
    this.sourceInUs = clamp(sourceInUs ?? 0, 0, mediaSource.durationUs);
    this.sourceOutUs = clamp(
      sourceOutUs ?? mediaSource.durationUs,
      this.sourceInUs,
      mediaSource.durationUs,
    );
    this.width = mediaSource.width;
    this.height = mediaSource.height;
    this.durationUs = this.sourceOutUs - this.sourceInUs;
    this.ringCapacity = ringCapacity;
    this.buffer = new FrameRingBuffer(ringCapacity);
  }

  async frameAt(clipTimeUs: TimeUs): Promise<VideoFrame | null> {
    if (this.disposed) return null;
    if (this.decoderError) throw this.decoderError;

    const mediaTime = this.sourceInUs + clamp(clipTimeUs, 0, this.durationUs);

    if (this.needsRepositionFor(mediaTime)) this.beginSeek(mediaTime);

    this.startPumpIfIdle();

    let candidate = this.buffer.pickAt(mediaTime);
    // A target behind everything buffered can never be satisfied by waiting —
    // the pump only decodes forward, so pickAt(mediaTime) will keep missing
    // for the full budget no matter how long we poll (this is the routine
    // case where the pump has raced a bit ahead of a real-time target within
    // the same GOP, not a rare edge case — polling anyway was burning the
    // full FRAME_WAIT_BUDGET_MS on a large fraction of calls and reading as
    // preview stutter). Go straight to the earliest-available fallback.
    if (!candidate && mediaTime < this.buffer.earliestPts()) {
      candidate = this.buffer.pickEarliest();
    }
    if (!candidate) {
      candidate = await this.waitForFrameAt(mediaTime, FRAME_WAIT_BUDGET_MS);
    }
    if (!candidate && this.buffer.size() > 0) {
      // Final fallback: caller asked for a time BEFORE the first producible
      // frame (e.g., target=0 on a video that starts at pts=266ms).
      candidate = this.buffer.pickEarliest();
    }
    if (candidate) {
      this.buffer.trimBefore(mediaTime - TRIM_BEHIND_US);
    }
    return candidate;
  }

  /**
   * Export-mode fetch: like frameAt, but WAIT until the decoder has produced a
   * frame at-or-past the target, so pickAt returns the exact display frame for
   * `clipTimeUs` rather than the best-buffered-so-far. The playback frameAt
   * never blocks (smooth scrub, tolerates lag); export is not real-time and
   * needs the exact frame, so it waits here.
   */
  async frameAtExact(clipTimeUs: TimeUs): Promise<VideoFrame | null> {
    if (this.disposed) return null;
    if (this.decoderError) throw this.decoderError;
    const mediaTime = this.sourceInUs + clamp(clipTimeUs, 0, this.durationUs);

    // Forward-only export never re-reads earlier times — evict everything
    // before the target UP FRONT (not just what the previous call's returned
    // candidate covered) so the ring has maximum free capacity for whatever
    // the pump delivers next. Decoder output can arrive in bursts rather than
    // steadily one-frame-at-a-time (e.g. when an encoder shares the main
    // thread with decode during export, starving the decoder's own output
    // callback until the thread frees up) — if stale leftover content is
    // still occupying ring slots when that burst lands, the overflow gets
    // silently dropped in the output callback, and this call ends up settling
    // for whatever stale frame survived instead of the target's own frame.
    this.buffer.trimBefore(mediaTime);

    if (this.needsRepositionFor(mediaTime)) this.beginSeek(mediaTime);
    this.startPumpIfIdle();

    const start = performance.now();
    while (!this.disposed && this.buffer.latestPts() < mediaTime) {
      if (this.decoderError) throw this.decoderError;
      // End of stream reached and pump idle → can't get any closer.
      if (this.seek && this.seek.cursor >= this.mediaSource.samples.length && !this.pumpRunning) {
        break;
      }
      if (performance.now() - start > EXACT_WAIT_BUDGET_MS) break;
      // Drain frames behind the target so the (capacity-bounded) pump always
      // has space to decode FORWARD toward the target — otherwise a full buffer
      // of sub-target frames deadlocks the pump and we'd spin to the budget.
      this.buffer.trimBefore(mediaTime - TRIM_BEHIND_US);
      // High-fps sources can pack more frames into the TRIM_BEHIND_US history
      // window than the ring can hold, so the time-based trim above frees
      // nothing and the pump deadlocks here — every frameAtExact then crawls
      // to EXACT_WAIT_BUDGET_MS (~3s/frame). Drop the oldest (only once
      // nothing usable is buffered yet) to let the pump decode toward the
      // target. Robust to any source fps (unlike bumping ring capacity, which
      // only moves the threshold).
      if (!this.buffer.hasSpace() && this.buffer.latestPts() < mediaTime) {
        this.buffer.dropOldest();
      }
      this.startPumpIfIdle();
      // Wake on the next decoded frame (no 4ms poll clamp), with a short
      // fallback in case the pump momentarily stalls.
      await new Promise<void>((resolve) => {
        let done = false;
        const finish = () => {
          if (done) return;
          done = true;
          unsub();
          clearTimeout(timer);
          resolve();
        };
        const unsub = this.onFrameAvailable(finish);
        const timer = setTimeout(finish, 100);
      });
    }

    const candidate = this.buffer.pickAt(mediaTime) ?? this.buffer.pickEarliest();
    // Forward-only export never re-reads earlier times, so drop everything
    // before the frame just returned (not the 200ms window, which can't evict
    // high-fps clusters). Frees the trailing slots so the pump rebuilds forward
    // lookahead between calls instead of pacing one frame per call.
    if (candidate) this.buffer.trimBefore(candidate.timestamp);
    return candidate;
  }

  onFrameAvailable(cb: () => void): () => void {
    this.frameAvailableSubs.add(cb);
    return () => {
      this.frameAvailableSubs.delete(cb);
    };
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.generation++;
    this.disposeDecoder();
    this.resetInFlight();
    this.frameAvailableSubs.clear();
    this.buffer.dispose();
  }

  // ────────────────────────────────────────────────────────── internals

  private needsRepositionFor(mediaTime: TimeUs): boolean {
    if (!this.seek) return true;
    const earliest = this.buffer.earliestPts();
    const latest = this.buffer.latestPts();
    // Buffer empty AND a seek is in flight → no reposition; pump will produce.
    if (!Number.isFinite(earliest) && this.pumpRunning) return false;
    if (!Number.isFinite(earliest)) return true;
    if (mediaTime < earliest || mediaTime > latest + FORWARD_LOOKAHEAD_US) {
      // Only a real reposition if the target now belongs to a DIFFERENT GOP
      // (a different nearest keyframe) than the one already being decoded.
      // Reseeking to the SAME keyframe we're already pumping from discards
      // all decode progress and restarts from scratch for no gain — if the
      // real-time target keeps outrunning a lagging-but-still-progressing
      // pump, this fires on nearly every call, so the pump is perpetually
      // reset before it ever gets an uninterrupted run to catch up. That
      // livelock is exactly what reads on screen as the picture "walking
      // forward a bit, then snapping back" while audio/timeline stay smooth.
      return this.mediaSource.index.findKeyframeAtOrBefore(mediaTime) !== this.seek.keyIdx;
    }
    return false;
  }

  private beginSeek(mediaTime: TimeUs): void {
    this.generation++;
    this.disposeDecoder();
    this.buffer.clear();
    // The old decoder is closed and abandons any decodes it had in flight
    // (their output callback will never fire), so their in-flight slots must
    // be released here — otherwise the count would drift upward forever
    // across seeks and eventually wedge the pump on a phantom backlog.
    this.resetInFlight();
    const keyIdx = this.mediaSource.index.findKeyframeAtOrBefore(mediaTime);
    this.seek = { cursor: keyIdx, keyIdx, targetMediaUs: mediaTime };
  }

  private startPumpIfIdle(): void {
    if (this.pumpRunning || this.disposed) return;
    if (!this.seek) return;
    if (this.seek.cursor >= this.mediaSource.samples.length) return;
    this.pumpRunning = true;
    void this.runPump(this.generation);
  }

  /**
   * True while fewer than ringCapacity decodes are outstanding (submitted to
   * the decoder but not yet resolved via its output callback). This is the
   * pump's real backpressure signal — see the `inFlight` field comment for
   * why `buffer.hasSpace()` alone can't do this job.
   */
  private hasInFlightSpace(): boolean {
    return this.inFlight < this.ringCapacity;
  }

  private awaitInFlightSpace(): Promise<void> {
    if (this.hasInFlightSpace()) return Promise.resolve();
    return new Promise((res) => this.inFlightWaiters.push(res));
  }

  private releaseInFlightSlot(): void {
    this.inFlight = Math.max(0, this.inFlight - 1);
    while (this.inFlightWaiters.length > 0 && this.hasInFlightSpace()) {
      this.inFlightWaiters.shift()!();
    }
  }

  private resetInFlight(): void {
    this.inFlight = 0;
    const waiters = this.inFlightWaiters;
    this.inFlightWaiters = [];
    for (const w of waiters) w();
  }

  private async runPump(myGeneration: number): Promise<void> {
    try {
      if (!this.decoder) this.initDecoder();
      if (!this.decoder) return;

      while (
        !this.disposed &&
        this.generation === myGeneration &&
        this.seek &&
        this.seek.cursor < this.mediaSource.samples.length
      ) {
        // Both caps matter: hasInFlightSpace() bounds decodes already
        // submitted-but-not-yet-resolved (the fix — async decoders resolve
        // later, so this is the only thing that stops the pump racing ahead
        // before the first output arrives); buffer.hasSpace() still matters
        // once outputs DO start resolving faster than the consumer drains
        // them (a synchronous/instant decoder resolves within the same
        // decode() call, so inFlight alone never blocks it — buffer.hasSpace()
        // is what bounds that case, exactly as it always has). Only await
        // whichever is ACTUALLY blocking — awaiting one that already has
        // space resolves immediately, so racing both when just one is full
        // would spin the loop with no real wait.
        const blockedOn: Array<Promise<void>> = [];
        if (!this.hasInFlightSpace()) blockedOn.push(this.awaitInFlightSpace());
        if (!this.buffer.hasSpace()) blockedOn.push(this.buffer.awaitSpace());
        if (blockedOn.length > 0) {
          await Promise.race(blockedOn);
          continue;
        }
        if (this.disposed || this.generation !== myGeneration || !this.seek) {
          break;
        }

        const samples = this.mediaSource.samples;
        const i = this.seek.cursor;
        const sample = samples[i]!;
        const isKey = i === this.seek.keyIdx;

        try {
          this.decoder.decode(
            new EncodedVideoChunk({
              type: isKey ? "key" : "delta",
              timestamp: sample.cts_us,
              duration: sample.duration_us,
              data: sample.data,
            }),
          );
          this.inFlight++;
        } catch (err) {
          this.decoderError = err instanceof Error ? err : new Error(String(err));
          break;
        }

        this.seek.cursor++;

        // Stop feeding past clip end, with a B-frame margin so output reaches
        // sourceOut.
        if (sample.cts_us >= this.sourceOutUs) {
          if (sample.cts_us >= this.sourceOutUs + 250_000) break;
        }

        // Yield occasionally so the output handler runs.
        if ((i & 0x7) === 0) {
          await yieldToEventLoop();
        }
      }
    } finally {
      this.pumpRunning = false;
    }
  }

  private initDecoder(): void {
    try {
      const decoder = new VideoDecoder({
        output: (frame) => {
          // A decode this callback resolves was counted against
          // hasInFlightSpace() when submitted — release its slot regardless
          // of what happens to the frame below (buffered, or dropped as
          // outside the clip window / a disposed reader).
          this.releaseInFlightSlot();
          // Drop frames outside the clip window (with margin).
          if (
            frame.timestamp < this.sourceInUs - 100_000 ||
            frame.timestamp > this.sourceOutUs + 250_000
          ) {
            frame.close();
            return;
          }
          if (this.disposed || !this.buffer.hasSpace()) {
            frame.close();
            return;
          }
          this.buffer.push(frame);
          for (const cb of this.frameAvailableSubs) cb();
        },
        error: (e) => {
          this.decoderError = e instanceof Error ? e : new Error(String(e));
        },
      });
      decoder.configure(this.mediaSource.config);
      this.decoder = decoder;
    } catch (err) {
      this.decoderError = err instanceof Error ? err : new Error(String(err));
      this.decoder = null;
    }
  }

  private disposeDecoder(): void {
    if (this.decoder) {
      try {
        this.decoder.close();
      } catch {
        // ignore
      }
      this.decoder = null;
    }
    this.decoderError = null;
  }

  private async waitForFrameAt(
    mediaTime: TimeUs,
    budgetMs: number,
  ): Promise<VideoFrame | null> {
    const start = performance.now();
    while (!this.disposed) {
      const candidate = this.buffer.pickAt(mediaTime);
      if (candidate) return candidate;
      if (this.decoderError) throw this.decoderError;
      if (performance.now() - start > budgetMs) return null;
      await new Promise<void>((res) => setTimeout(res, 8));
    }
    return null;
  }

  /** Force a flush + return success or timeout (used by diagnostics/tests). */
  async flushDecoder(timeoutMs: number = FLUSH_TIMEOUT_MS): Promise<void> {
    const dec = this.decoder;
    if (!dec) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    try {
      await Promise.race([
        dec.flush(),
        new Promise<never>((_, reject) => {
          timer = setTimeout(() => {
            reject(
              new EngineError(
                `decoder.flush() timed out after ${timeoutMs}ms`,
                "FLUSH_TIMEOUT",
              ),
            );
          }, timeoutMs);
        }),
      ]);
    } finally {
      if (timer !== null) clearTimeout(timer);
    }
  }
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}
