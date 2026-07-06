/**
 * SourceTab — the news_video source-video slot. Acquire a source either by local
 * file import (vc:pickVideo → copy/cut) or yt-dlp download (URL → download), both
 * as sidecar jobs (material.set_source) consumed via runJob. Faithful to the Tk
 * source_add_dialog (origin link|local + optional clip range) + source_prepare_modal
 * (category-keyed recovery hints).
 */

import { useCallback, useEffect, useState } from "react";
import { sourceAudioPath } from "@materials/news_video/paths.js";
import { rpc, RpcError, type AcquireSource, type SourceMeta } from "../../ipc/client";
import { useJob } from "../../ipc/runJob";
import { tr } from "../../i18n/tr";

export interface MaterialTabProps {
  type: string;
  instance: string;
  refreshKey: number;
  onChanged: () => void;
}

// AcquireError category (prefix of the failed job's message) → i18n key suffix.
const CATEGORY_KEYS: Record<string, string> = {
  network: "material.source.hint.network",
  url_invalid: "material.source.hint.url_invalid",
  js_runtime: "material.source.hint.js_runtime",
  cookies: "material.source.hint.cookies",
  disk: "material.source.hint.disk",
  ffmpeg: "material.source.hint.ffmpeg",
  other: "material.source.hint.other",
};

function hintFor(error: string): string {
  const cat = error.split(":", 1)[0]?.trim();
  const key = cat && CATEGORY_KEYS[cat];
  return key ? tr(key) : error;
}

function fmtDuration(sec?: number): string {
  if (!sec || sec <= 0) return "";
  const s = Math.floor(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}` : `${m}:${String(ss).padStart(2, "0")}`;
}

function fmtNativeError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

const INPUT: React.CSSProperties = {
  padding: "4px 8px",
  background: "#1a1a1e",
  color: "#ddd",
  border: "1px solid #333",
  borderRadius: 4,
  fontSize: 13,
};
const BTN: React.CSSProperties = {
  padding: "6px 14px",
  background: "#2d6cdf",
  color: "#fff",
  border: "none",
  borderRadius: 5,
  fontSize: 13,
  cursor: "pointer",
};
const BTN_GHOST: React.CSSProperties = {
  ...BTN,
  background: "#2a2a2e",
  color: "#ddd",
};
const ROW_BTN: React.CSSProperties = {
  background: "#2a2a2e",
  color: "#ccc",
  border: "1px solid #3a3a40",
  borderRadius: 4,
  padding: "1px 6px",
  fontSize: 12,
  cursor: "pointer",
};
const PATH_TEXT: React.CSSProperties = {
  color: "#ddd",
  fontSize: 12,
  wordBreak: "break-all",
};

export function SourceTab({ type, instance, refreshKey, onChanged }: MaterialTabProps) {
  const [meta, setMeta] = useState<SourceMeta | null>(null);
  const [filled, setFilled] = useState(false);
  const [srcUrl, setSrcUrl] = useState("");
  const [sourcePath, setSourcePath] = useState("");
  const [mp3Path, setMp3Path] = useState("");
  const [mp3Mtime, setMp3Mtime] = useState<number | null>(null);
  const [mp3Busy, setMp3Busy] = useState(false);
  const [mp3Error, setMp3Error] = useState("");
  const [mode, setMode] = useState<"local" | "link">("local");
  const [url, setUrl] = useState("");
  const [useRange, setUseRange] = useState(false);
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [reimport, setReimport] = useState(false);
  const [loadErr, setLoadErr] = useState("");
  const job = useJob();

  const reload = useCallback(async () => {
    setLoadErr("");
    try {
      const [m, r] = await Promise.all([
        rpc.materialSourceMeta(type, instance),
        rpc.slotReadiness(type, instance),
      ]);
      setMeta(m);
      const isFilled = r.source?.isFilled ?? false;
      setFilled(isFilled);
      if (isFilled) {
        const path = await rpc.getArtifact(type, instance, "source");
        setSourcePath(path ?? "");
        setSrcUrl(path ? window.vc.mediaUrl(path) : "");
        const audioPath = await rpc.getArtifact(type, instance, "source_audio");
        setMp3Path(audioPath ?? "");
        if (audioPath) {
          const st = await window.vc.fs.stat(audioPath);
          setMp3Mtime(st.mtimeMs ?? null);
        } else {
          setMp3Mtime(null);
        }
      } else {
        setSourcePath("");
        setSrcUrl("");
        setMp3Path("");
        setMp3Mtime(null);
      }
    } catch (err) {
      setLoadErr(err instanceof RpcError ? `[${err.code}] ${err.message}` : String(err));
    }
  }, [type, instance]);

  useEffect(() => {
    void reload();
  }, [reload, refreshKey]);

  const rangeParams = useCallback((): Pick<AcquireSource, "clip_range"> => {
    if (useRange && rangeStart.trim() && rangeEnd.trim()) {
      return { clip_range: { start: rangeStart.trim(), end: rangeEnd.trim() } };
    }
    return {};
  }, [useRange, rangeStart, rangeEnd]);

  const acquire = useCallback(
    async (source: AcquireSource) => {
      const res = await job.run<{ title?: string; duration_sec?: number; width?: number; height?: number }>(
        () => rpc.startSetSource(type, instance, source),
      );
      if (res !== undefined) {
        // capability.acquire_source is plugin-agnostic and stamps no project meta,
        // so persist the source descriptor + probe values here (ADR-0008 B3.2b).
        // Non-fatal: the file is already on disk, so the source must still show
        // (and the picker must reset) even if the meta stamp fails — otherwise a
        // commit error would make the just-downloaded video "disappear".
        if (type === "news_video") {
          try {
            await rpc.commitSource(source, {
              ...(res.title !== undefined ? { title: res.title } : {}),
              ...(res.duration_sec !== undefined ? { durationSec: res.duration_sec } : {}),
              ...(res.width !== undefined ? { width: res.width } : {}),
              ...(res.height !== undefined ? { height: res.height } : {}),
            });
          } catch (err) {
            setLoadErr(err instanceof RpcError ? `[${err.code}] ${err.message}` : String(err));
          }
        }
        try {
          const instanceDir = await rpc.materialInstanceDir(type, instance);
          await window.vc.fs.remove(sourceAudioPath(instanceDir));
        } catch {
          /* stale generated audio is best-effort cleanup */
        }
        setReimport(false);
        onChanged();
        await reload();
      }
    },
    [job, type, instance, onChanged, reload],
  );

  const acquireLocal = useCallback(async () => {
    const path = await window.vc.pickVideo();
    if (!path) return;
    await acquire({ origin: "local", imported_from: path, ...rangeParams() });
  }, [acquire, rangeParams]);

  const acquireLink = useCallback(async () => {
    if (!url.trim()) return;
    await acquire({ origin: "link", url: url.trim(), ...rangeParams() });
  }, [acquire, url, rangeParams]);

  const generateMp3 = useCallback(async () => {
    if (!sourcePath || mp3Busy) return;
    setMp3Busy(true);
    setMp3Error("");
    try {
      const instanceDir = await rpc.materialInstanceDir(type, instance);
      const outputPath = sourceAudioPath(instanceDir);
      const out = await window.vc.extractMp3({ inputPath: sourcePath, outputPath });
      setMp3Path(out);
      const st = await window.vc.fs.stat(out);
      setMp3Mtime(st.mtimeMs ?? null);
    } catch (err) {
      setMp3Error(fmtNativeError(err));
    } finally {
      setMp3Busy(false);
    }
  }, [type, instance, sourcePath, mp3Busy]);

  const playMp3 = useCallback(() => {
    if (mp3Path) void window.vc.openPath(mp3Path);
  }, [mp3Path]);

  const locateMp3 = useCallback(() => {
    if (mp3Path) void window.vc.showInFolder(mp3Path);
  }, [mp3Path]);

  const showPicker = !filled || reimport;

  return (
    <div style={{ maxWidth: 560, display: "flex", flexDirection: "column", gap: 14 }}>
      {loadErr && <div style={{ color: "#ff6b6b", fontSize: 12 }}>✗ {loadErr}</div>}

      {/* Acquired-source summary card */}
      {filled && (
        <div style={{ padding: "10px 12px", background: "#1c1c20", borderRadius: 6, border: "1px solid #2a2a2e" }}>
          <div style={{ color: "#7fd17f", fontSize: 13, marginBottom: 4 }}>
            ✓ {meta?.title || "video.mp4"}
          </div>
          <div style={{ color: "#999", fontSize: 12 }}>
            {[
              meta?.duration_sec ? fmtDuration(meta.duration_sec) : "",
              meta?.width && meta?.height ? `${meta.width}×${meta.height}` : "",
              meta?.origin === "link" ? meta.url : meta?.imported_from,
            ]
              .filter(Boolean)
              .join("  ·  ")}
          </div>
          {srcUrl && (
            <video
              src={srcUrl}
              controls
              style={{ display: "block", marginTop: 8, maxWidth: "100%", maxHeight: 300, borderRadius: 4, background: "#000" }}
            />
          )}
          {!reimport && (
            <button onClick={() => setReimport(true)} style={{ ...BTN_GHOST, marginTop: 8, padding: "4px 10px", fontSize: 12 }}>
              {tr("material.source.reimport_btn")}
            </button>
          )}
        </div>
      )}

      {filled && (
        <div style={{ padding: "10px 12px", background: "#1c1c20", borderRadius: 6, border: "1px solid #2a2a2e" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <div style={{ color: "#ddd", fontSize: 13, fontWeight: 600 }}>{tr("material.source.mp3_title")}</div>
            {mp3Path && mp3Mtime !== null && (
              <span style={{ color: "#777", fontSize: 12 }}>{new Date(mp3Mtime).toISOString()}</span>
            )}
            <button
              onClick={() => void generateMp3()}
              disabled={!sourcePath || mp3Busy}
              style={{ ...BTN, marginLeft: "auto", padding: "4px 10px", fontSize: 12 }}
            >
              {mp3Busy
                ? tr("material.source.mp3_generating")
                : mp3Path
                  ? tr("material.source.mp3_regenerate")
                  : tr("material.source.mp3_generate")}
            </button>
          </div>
          {mp3Path ? (
            <>
              <audio
                key={mp3Mtime ?? mp3Path}
                src={`${window.vc.mediaUrl(mp3Path)}?v=${encodeURIComponent(String(mp3Mtime ?? ""))}`}
                controls
                style={{ display: "block", width: "100%", marginBottom: 8 }}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ ...PATH_TEXT, flex: 1 }}>{mp3Path}</span>
                <button onClick={playMp3} style={ROW_BTN} title={tr("material.source.mp3_play")}>
                  ▶
                </button>
                <button onClick={locateMp3} style={ROW_BTN} title={tr("material.source.mp3_locate")}>
                  📁
                </button>
              </div>
            </>
          ) : (
            <div style={{ color: "#888", fontSize: 12 }}>{tr("material.source.mp3_empty")}</div>
          )}
          {mp3Error && <div style={{ color: "#ff6b6b", fontSize: 12, marginTop: 8 }}>✗ {mp3Error}</div>}
        </div>
      )}

      {/* Acquisition picker */}
      {showPicker && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {filled && reimport && (
            <div style={{ color: "#d9a441", fontSize: 12 }}>⚠ {tr("material.source.reimport_warn")}</div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <ModeBtn label={tr("material.source.mode_local")} active={mode === "local"} onClick={() => setMode("local")} />
            <ModeBtn label={tr("material.source.mode_link")} active={mode === "link"} onClick={() => setMode("link")} />
          </div>

          {mode === "link" && (
            <input
              value={url}
              placeholder={tr("material.source.url_placeholder")}
              disabled={job.running}
              onChange={(e) => setUrl(e.target.value)}
              style={{ ...INPUT, width: "100%", boxSizing: "border-box" }}
            />
          )}

          {/* Optional clip range */}
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#bbb" }}>
            <input type="checkbox" checked={useRange} disabled={job.running} onChange={(e) => setUseRange(e.target.checked)} />
            {tr("material.source.clip_range_label")}
          </label>
          {useRange && (
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input value={rangeStart} placeholder={tr("material.source.range_start_placeholder")} disabled={job.running} onChange={(e) => setRangeStart(e.target.value)} style={{ ...INPUT, width: 110 }} />
              <span style={{ color: "#666" }}>→</span>
              <input value={rangeEnd} placeholder={tr("material.source.range_end_placeholder")} disabled={job.running} onChange={(e) => setRangeEnd(e.target.value)} style={{ ...INPUT, width: 110 }} />
            </div>
          )}

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {mode === "local" ? (
              <button onClick={() => void acquireLocal()} disabled={job.running} style={BTN}>
                {tr("material.source.pick_local_btn")}
              </button>
            ) : (
              <button onClick={() => void acquireLink()} disabled={job.running || !url.trim()} style={BTN}>
                {tr("material.source.download_btn")}
              </button>
            )}
            {filled && reimport && (
              <button onClick={() => setReimport(false)} disabled={job.running} style={BTN_GHOST}>
                {tr("common.cancel")}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Progress + cancel */}
      {job.running && (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, color: "#4a9eff" }}>
            {job.progress?.status_text || job.progress?.phase || tr("material.source.processing")}
            {job.progress?.pct != null ? ` · ${Math.round(job.progress.pct)}%` : ""}
          </span>
          <button onClick={job.cancel} style={{ ...BTN_GHOST, padding: "3px 10px", fontSize: 12 }}>
            {tr("common.cancel")}
          </button>
        </div>
      )}

      {job.error && <div style={{ color: "#ff6b6b", fontSize: 12 }}>✗ {hintFor(job.error)}</div>}
    </div>
  );
}

function ModeBtn(props: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={props.onClick}
      style={{
        padding: "5px 12px",
        background: props.active ? "#2d6cdf" : "#2a2a2e",
        color: props.active ? "#fff" : "#bbb",
        border: "none",
        borderRadius: 5,
        fontSize: 12,
        cursor: "pointer",
      }}
    >
      {props.label}
    </button>
  );
}
