import { describe, it, expect } from "vitest";
import { isSupportedCodec } from "./Demuxer";

/**
 * Regression test for the "Codec vp09.00.40.08 not supported" bug: the
 * download pipeline deliberately leaves video codec unconstrained
 * (source_acquire.py) so YouTube can serve AV1 (smaller) when available, and
 * falls back to VP9 when it isn't. isSupportedCodec previously only knew
 * about H.264/HEVC/AV1, so a VP9 source hard-failed at demux time even
 * though WebCodecs itself decodes VP9 fine.
 */
describe("isSupportedCodec", () => {
  it("accepts H.264", () => {
    expect(isSupportedCodec("avc1.640028")).toBe(true);
    expect(isSupportedCodec("avc3.640028")).toBe(true);
  });

  it("accepts HEVC", () => {
    expect(isSupportedCodec("hvc1.1.6.L93.90")).toBe(true);
    expect(isSupportedCodec("hev1.1.6.L93.90")).toBe(true);
  });

  it("accepts AV1", () => {
    expect(isSupportedCodec("av01.0.08M.08")).toBe(true);
  });

  it("accepts VP9 and VP8", () => {
    expect(isSupportedCodec("vp09.00.40.08")).toBe(true);
    expect(isSupportedCodec("vp08.00.40.08")).toBe(true);
  });

  it("rejects unknown codecs", () => {
    expect(isSupportedCodec("mp4v.20.9")).toBe(false);
    expect(isSupportedCodec("")).toBe(false);
  });
});
