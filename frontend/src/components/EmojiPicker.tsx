import React, { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";

const EMOJIS = [
  { emoji: "😊", label: "calm" },
  { emoji: "🎉", label: "party" },
  { emoji: "😳", label: "surprised" },
  { emoji: "🌧️", label: "rainy" },
  { emoji: "💪", label: "energetic" },
  { emoji: "🦁", label: "bold" },
  { emoji: "☕", label: "chill" },
  { emoji: "🌙", label: "night" },
  { emoji: "🚗", label: "driving" },
  { emoji: "📚", label: "study" },
  { emoji: "🍷", label: "relaxed" },
  { emoji: "🚶‍♂️", label: "walk" },
  { emoji: "🌊", label: "waves" },
  { emoji: "🎸", label: "rock" },
  { emoji: "🎹", label: "piano" },
  { emoji: "💜", label: "love" },
];

interface EmojiPickerProps {
  value: string[];
  onChange: (emojis: string[]) => void;
}

export function EmojiPicker({ value, onChange }: EmojiPickerProps) {
  const [showAll, setShowAll] = useState(false);
  const [visibleCount, setVisibleCount] = useState(8);

  useEffect(() => {
    const updateCount = () => {
      const w = window.innerWidth;
      if (w < 640) {
        setVisibleCount(6);
      } else if (w < 1024) {
        setVisibleCount(8);
      } else {
        setVisibleCount(10);
      }
    };
    updateCount();
    window.addEventListener("resize", updateCount);
    return () => window.removeEventListener("resize", updateCount);
  }, []);

  const visibleEmojis = useMemo(() => EMOJIS.slice(0, visibleCount), [visibleCount]);

  const handleToggle = (emoji: string) => {
    if (value.includes(emoji)) {
      onChange(value.filter((e) => e !== emoji));
    } else {
      onChange([...value, emoji]);
    }
  };

  const renderEmojiButton = (emoji: string, label: string, sizeClasses = "w-12 h-12 sm:w-14 sm:h-14") => (
    <button
      key={emoji}
      onClick={() => handleToggle(emoji)}
      className={`${sizeClasses} rounded-xl transition-all duration-200 hover:scale-105 ${
        value.includes(emoji)
          ? "bg-indigo-500/20 ring-2 ring-indigo-500 shadow-lg shadow-indigo-500/30"
          : "bg-white/5 hover:bg-white/10 border border-white/10"
      }`}
      title={label}
    >
      <span className="text-lg sm:text-xl">{emoji}</span>
    </button>
  );

  return (
    <div className="space-y-4">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((emoji) => (
            <button
              key={emoji}
              onClick={() => handleToggle(emoji)}
              className="group inline-flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1.5 text-sm transition-all hover:border-indigo-500/50 hover:bg-indigo-500/20"
            >
              <span>{emoji}</span>
              <X className="h-3 w-3 text-indigo-300 opacity-0 transition-opacity group-hover:opacity-100" />
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-10 sm:grid-cols-10 gap-1 sm:gap-1.5">
        {visibleEmojis.map(({ emoji, label }) => renderEmojiButton(emoji, label))}
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="w-12 h-12 sm:w-14 sm:h-14 rounded-xl border border-dashed border-indigo-400/60 bg-white/5 text-indigo-200 font-bold text-lg hover:bg-white/10 transition"
          title="See all emojis"
        >
          +
        </button>
      </div>

      {showAll && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4" onClick={() => setShowAll(false)}>
          <div
            className="w-full max-w-2xl rounded-2xl border border-white/15 bg-[#0f1224] p-5 shadow-2xl shadow-black/40"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-white font-semibold">All emojis</h3>
              <button
                onClick={() => setShowAll(false)}
                className="rounded-full border border-white/20 text-white px-3 py-1 text-sm hover:bg-white/10 transition"
              >
                Close
              </button>
            </div>
            <div className="grid grid-cols-5 sm:grid-cols-6 gap-2">
              {EMOJIS.map(({ emoji, label }) => renderEmojiButton(emoji, label, "w-12 h-12"))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
