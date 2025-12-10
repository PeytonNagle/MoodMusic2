import { useEffect, useMemo, useRef, useState } from "react";

interface EmojiPickerProps {
  value: string[];
  onChange: (next: string[]) => void;
}

const BASE_EMOJIS = ["🙂", "😮", "😌", "🔥", "😴", "🎉", "😢", "❤️", "🤖", "☕", "🧠", "💪"];
const MORE_EMOJIS = [
  "😀",
  "😊",
  "😉",
  "😭",
  "😡",
  "🤔",
  "🤗",
  "🤩",
  "🥳",
  "😎",
  "😇",
  "🤘",
  "🎶",
  "🎧",
  "🎸",
  "🎤",
  "🥁",
  "💃",
  "🕺",
  "🏃",
  "☀️",
  "🌙",
  "🌧️",
  "🌊",
  "🏔️",
  "🌅",
  "🌃",
  "🍃",
  "🍂",
  "🔥",
  "💤",
  "🧘",
  "🏋️",
  "🏄",
  "🚴",
  "☕",
  "🥤",
];
const MAX_EMOJIS = 12;
const ALL_EMOJIS = Array.from(new Set([...BASE_EMOJIS, ...MORE_EMOJIS]));

export function EmojiPicker({ value, onChange }: EmojiPickerProps) {
  const selectedSet = useMemo(() => new Set(value), [value]);
  const [isExpanded, setIsExpanded] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);

  const toggleEmoji = (emoji: string) => {
    const isSelected = selectedSet.has(emoji);
    if (isSelected) {
      onChange(value.filter((e) => e !== emoji));
      return;
    }
    if (value.length >= MAX_EMOJIS) return;
    onChange([...value, emoji]);
  };

  const clearEmojis = () => {
    if (value.length) {
      onChange([]);
    }
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        popoverRef.current &&
        containerRef.current &&
        !popoverRef.current.contains(target) &&
        !containerRef.current.contains(target)
      ) {
        setIsExpanded(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const renderEmojiButton = (emoji: string) => {
    const isSelected = selectedSet.has(emoji);
    return (
      <button
        key={emoji}
        type="button"
        onClick={() => toggleEmoji(emoji)}
        aria-pressed={isSelected}
        className={`w-10 h-10 rounded-xl border transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 focus:ring-offset-2 focus:ring-offset-transparent flex items-center justify-center ${
          isSelected
            ? "bg-white text-black border-white shadow-[0_0_18px_rgba(255,255,255,0.45)] hover:bg-white active:bg-white"
            : "bg-white/5 border-white/10 hover:border-purple-400/40"
        }`}
        style={
          isSelected
            ? { backgroundColor: "#ffffff", color: "#0f172a" }
            : undefined
        }
      >
        <span className={`text-xl leading-none block ${isSelected ? "text-black" : ""}`}>{emoji}</span>
      </button>
    );
  };

  return (
    <div className="flex flex-col gap-3 relative w-full" ref={containerRef}>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between text-sm text-gray-400">
        <span className="leading-snug">Tag the vibe with emojis (optional)</span>
        <button
          type="button"
          onClick={clearEmojis}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          disabled={!value.length}
        >
          Clear
        </button>
      </div>
      <div
        className="min-h-[40px] flex flex-wrap gap-1.5 rounded-xl bg-white/5 border border-white/10 px-2 py-2"
        style={{ columnGap: "0.4rem", rowGap: "0.4rem", maxWidth: "100%" }}
      >
        {value.length === 0 ? (
          <span className="text-xs text-gray-500">No emojis selected</span>
        ) : (
          value.map((emoji) => (
            <button
              key={emoji}
              type="button"
              onClick={() => toggleEmoji(emoji)}
              className="px-1.5 py-0.5 rounded-full bg-white text-xs text-black shadow flex items-center justify-center"
            >
              {emoji}
            </button>
          ))
        )}
      </div>
      <div className="flex">
        <button
          type="button"
          aria-haspopup="dialog"
          aria-expanded={isExpanded}
          onClick={() => setIsExpanded((prev) => !prev)}
          className="w-full sm:w-auto rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm text-gray-200 hover:text-white hover:border-purple-300 transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 focus:ring-offset-2 focus:ring-offset-transparent"
        >
          {isExpanded ? "Hide emoji palette" : "Choose emojis"}
        </button>
      </div>
      {isExpanded && (
        <div
          ref={popoverRef}
          className="absolute z-50 mt-2 left-0 sm:right-0 top-full rounded-2xl shadow-2xl overflow-hidden w-full sm:w-auto"
          style={{
            backgroundColor: "#050914",
            width: "min(320px, calc(100vw - 2rem))",
            boxShadow: "0 22px 70px rgba(0,0,0,0.6)",
            opacity: 1,
            backdropFilter: "none",
            border: "1px solid rgba(255,255,255,0.08)",
            zIndex: 9999,
            pointerEvents: "auto",
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-gray-300">More emojis</span>
            <button
              type="button"
              onClick={() => setIsExpanded(false)}
              className="text-xs text-gray-400 hover:text-white px-2"
              aria-label="Close emoji picker"
            >
              X
            </button>
          </div>
          <div
            className="max-h-52 overflow-y-auto pr-1"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
              gap: "0.5rem",
              paddingBottom: "0.1rem",
              justifyItems: "center",
              alignItems: "center",
            }}
          >
            {ALL_EMOJIS.map((emoji) => renderEmojiButton(emoji))}
          </div>
        </div>
      )}
    </div>
  );
}
