import { useMemo } from "react";

interface EmojiPickerProps {
  value: string[];
  onChange: (next: string[]) => void;
}

const EMOJIS = ["🙂", "😮", "😌", "🔥", "😴", "🎉", "😢", "❤️", "🤖", "☕", "🧠", "💪"];
const MAX_EMOJIS = 12;

export function EmojiPicker({ value, onChange }: EmojiPickerProps) {
  const selectedSet = useMemo(() => new Set(value), [value]);

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

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-sm text-gray-400">
        <span>Tag the vibe with emojis (optional)</span>
        <button
          type="button"
          onClick={clearEmojis}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          disabled={!value.length}
        >
          Clear
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {EMOJIS.map((emoji) => {
          const isSelected = selectedSet.has(emoji);
          return (
            <button
              key={emoji}
              type="button"
              onClick={() => toggleEmoji(emoji)}
              aria-pressed={isSelected}
              className={`w-10 h-10 rounded-xl border transition-all focus:outline-none focus:ring-2 focus:ring-purple-400 focus:ring-offset-2 focus:ring-offset-transparent ${
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
              <span className={`text-xl leading-none ${isSelected ? "text-black" : ""}`}>{emoji}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
