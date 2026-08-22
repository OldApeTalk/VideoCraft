/**
 * Detail lists for the news_desk Style tab — the views the generic primitive
 * PropertyPanel can't render, filling the gap the legacy Tk panels had
 * (task.md 续28):
 *   - SubtitleCueList — the selected subtitle's snapshot SRT cues (start · text),
 *     read-only, click-to-seek.
 *   - ChapterScheduleList — the imported chapter rows (start · title),
 *     click-to-seek AND click-to-edit: clicking a row seeks the preview there
 *     and opens an editor below for that row's fields (title / refined /
 *     key_points / start / end). Edits patch the component's own `schedule`
 *     snapshot via onEditRow — never the source analysis.json — so a
 *     re-import (which re-snapshots from there) is the deliberate "undo"
 *     path, not a separate revert feature.
 *
 * news_desk composes the WHOLE source (identity time map), so a cue/chapter's
 * source-time start is also its output-time position — seeking straight to it
 * is correct.
 */

import { useState } from "react";
import type { SourceCue } from "@composition/components/index.js";
import type { NewsDeskChapterRow } from "@creations/news_desk/types.js";
import { formatTimestamp, parseTimestamp } from "@creations/clip/mapping.js";
import { tr } from "../../i18n/tr";

const panel: React.CSSProperties = {
  border: "1px solid #2a2a2e",
  borderRadius: 6,
  padding: "8px 10px",
  marginTop: 12,
};
const legendStyle: React.CSSProperties = { color: "#888", fontSize: 11, padding: "0 4px" };
const listBox: React.CSSProperties = {
  maxHeight: 180,
  overflow: "auto",
  background: "#161618",
  borderRadius: 4,
  padding: "2px 0",
};
const rowBtn: React.CSSProperties = {
  display: "flex",
  gap: 8,
  alignItems: "baseline",
  width: "100%",
  textAlign: "left",
  background: "transparent",
  border: "none",
  borderBottom: "1px solid #1f1f22",
  padding: "4px 8px",
  cursor: "pointer",
  fontSize: 12,
  color: "#ccc",
};
const tsCol: React.CSSProperties = {
  flex: "0 0 auto",
  color: "#6fa8ff",
  fontFamily: "Consolas, monospace",
  fontVariantNumeric: "tabular-nums",
};
const textCol: React.CSSProperties = {
  flex: 1,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const emptyStyle: React.CSSProperties = { color: "#666", fontSize: 12, padding: "6px 8px" };

/** Selected subtitle's cue list (read-only, click row to seek). */
export function SubtitleCueList(props: {
  cues: readonly SourceCue[] | undefined;
  onSeek: (sec: number) => void;
}) {
  const { cues, onSeek } = props;
  return (
    <fieldset style={panel}>
      <legend style={legendStyle}>{tr("news_desk.detail.subtitle_legend")}{cues && cues.length ? `（${cues.length}）` : ""}</legend>
      <div style={listBox}>
        {!cues || cues.length === 0 ? (
          <div style={emptyStyle}>{tr("news_desk.detail.subtitle_empty")}</div>
        ) : (
          cues.map((c, i) => (
            <button key={i} onClick={() => onSeek(c.sourceStart)} style={rowBtn} title={tr("news_desk.detail.seek_here")}>
              <span style={tsCol}>{formatTimestamp(c.sourceStart)}</span>
              <span style={textCol}>{c.text}</span>
            </button>
          ))
        )}
      </div>
    </fieldset>
  );
}

const selectedRowBtn: React.CSSProperties = { ...rowBtn, background: "#1d2740" };
const editorPanel: React.CSSProperties = {
  border: "1px solid #2a2a2e",
  borderRadius: 6,
  padding: "8px 10px",
  marginTop: 8,
  background: "#161618",
};
const editorLabel: React.CSSProperties = {
  width: 40,
  flexShrink: 0,
  color: "#999",
  fontSize: 12,
  paddingTop: 4,
};
const editorEntry: React.CSSProperties = {
  background: "#1a1a1e",
  color: "#ddd",
  border: "1px solid #333",
  borderRadius: 4,
  padding: "3px 6px",
  fontSize: 12,
  flex: 1,
  fontFamily: "inherit",
};

/** Imported chapter schedule. Click a row to seek the preview there AND open
 * an editor below for that row (click again to close). */
export function ChapterScheduleList(props: {
  schedule: NewsDeskChapterRow[] | undefined;
  onSeek: (sec: number) => void;
  onEditRow: (index: number, patch: Partial<NewsDeskChapterRow>) => void;
}) {
  const { schedule, onSeek, onEditRow } = props;
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const editRow = editIndex !== null ? schedule?.[editIndex] : undefined;

  return (
    <fieldset style={panel}>
      <legend style={legendStyle}>{tr("news_desk.detail.chapter_legend")}{schedule && schedule.length ? `（${schedule.length}）` : ""}</legend>
      <div style={listBox}>
        {!schedule || schedule.length === 0 ? (
          <div style={emptyStyle}>{tr("news_desk.detail.chapter_empty")}</div>
        ) : (
          schedule.map((row, i) => (
            <button
              key={i}
              onClick={() => {
                onSeek(row.start_sec);
                setEditIndex((cur) => (cur === i ? null : i));
              }}
              style={editIndex === i ? selectedRowBtn : rowBtn}
              title={tr("news_desk.detail.seek_here")}
            >
              <span style={tsCol}>{formatTimestamp(row.start_sec)}</span>
              <span style={textCol}>{row.title || tr("news_desk.detail.chapter_no_title")}</span>
            </button>
          ))
        )}
      </div>
      {editRow && (
        <ChapterRowEditor
          key={editIndex}
          row={editRow}
          onCommit={(patch) => onEditRow(editIndex!, patch)}
        />
      )}
    </fieldset>
  );
}

/** Editor for one chapter row — local text state, committed on blur/Enter
 * (mirrors ClipDetailPanel's pattern). Resets whenever the selected row
 * changes (the `key={editIndex}` on the caller side remounts this instead of
 * relying on a prop-change effect, since switching rows should always start
 * from that row's current values, never linger with the previous row's
 * in-progress edit). */
function ChapterRowEditor(props: {
  row: NewsDeskChapterRow;
  onCommit: (patch: Partial<NewsDeskChapterRow>) => void;
}) {
  const { row, onCommit } = props;
  const [startText, setStartText] = useState(formatTimestamp(row.start_sec));
  const [endText, setEndText] = useState(formatTimestamp(row.end_sec));
  const [titleText, setTitleText] = useState(row.title ?? "");
  const [refinedText, setRefinedText] = useState(row.refined ?? "");
  const [keyPointsText, setKeyPointsText] = useState((row.key_points ?? []).join("\n"));

  const commitStart = () => {
    const secs = Math.max(0, parseTimestamp(startText));
    setStartText(formatTimestamp(secs));
    if (Math.abs(secs - row.start_sec) > 1e-3) onCommit({ start_sec: secs });
  };
  const commitEnd = () => {
    const secs = Math.max(0, parseTimestamp(endText));
    setEndText(formatTimestamp(secs));
    if (Math.abs(secs - row.end_sec) > 1e-3) onCommit({ end_sec: secs });
  };
  const commitTitle = () => {
    if (titleText !== row.title) onCommit({ title: titleText });
  };
  const commitRefined = () => {
    if (refinedText !== row.refined) onCommit({ refined: refinedText });
  };
  const commitKeyPoints = () => {
    const points = keyPointsText.split("\n").map((s) => s.trim()).filter(Boolean);
    onCommit({ key_points: points });
  };

  return (
    <fieldset style={editorPanel}>
      <legend style={legendStyle}>{tr("news_desk.detail.chapter_edit_legend")}</legend>
      <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1 }}>
          <span style={editorLabel}>{tr("news_desk.detail.chapter_start_label")}</span>
          <input
            value={startText}
            onChange={(e) => setStartText(e.target.value)}
            onBlur={commitStart}
            onKeyDown={(e) => e.key === "Enter" && commitStart()}
            style={{ ...editorEntry, fontVariantNumeric: "tabular-nums" }}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1 }}>
          <span style={editorLabel}>{tr("news_desk.detail.chapter_end_label")}</span>
          <input
            value={endText}
            onChange={(e) => setEndText(e.target.value)}
            onBlur={commitEnd}
            onKeyDown={(e) => e.key === "Enter" && commitEnd()}
            style={{ ...editorEntry, fontVariantNumeric: "tabular-nums" }}
          />
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
        <span style={editorLabel}>{tr("news_desk.detail.chapter_title_label")}</span>
        <input
          value={titleText}
          onChange={(e) => setTitleText(e.target.value)}
          onBlur={commitTitle}
          onKeyDown={(e) => e.key === "Enter" && commitTitle()}
          style={editorEntry}
        />
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        <span style={editorLabel}>{tr("news_desk.detail.chapter_refined_label")}</span>
        <textarea
          value={refinedText}
          onChange={(e) => setRefinedText(e.target.value)}
          onBlur={commitRefined}
          rows={2}
          style={{ ...editorEntry, resize: "vertical" }}
        />
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <span style={editorLabel}>{tr("news_desk.detail.chapter_key_points_label")}</span>
        <textarea
          value={keyPointsText}
          onChange={(e) => setKeyPointsText(e.target.value)}
          onBlur={commitKeyPoints}
          placeholder={tr("news_desk.detail.chapter_key_points_hint")}
          rows={3}
          style={{ ...editorEntry, resize: "vertical" }}
        />
      </div>
    </fieldset>
  );
}
