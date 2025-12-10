import React from "react";
import { Search, Sparkles } from "lucide-react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { EmojiPicker } from "./EmojiPicker";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  isLoading?: boolean;
  loadingLabel?: string;
  selectedEmojis: string[];
  onChangeEmojis: (next: string[]) => void;
  songLimit: number;
  onChangeSongLimit: (limit: number) => void;
  popularityLabel: string;
  popularityRanges: Record<string, [number, number] | null>;
  onChangePopularity: (label: string) => void;
}

export function SearchInput({
  value,
  onChange,
  onSearch,
  isLoading,
  loadingLabel,
  selectedEmojis,
  onChangeEmojis,
  songLimit,
  onChangeSongLimit,
  popularityLabel,
  popularityRanges,
  onChangePopularity,
}: SearchInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSearch();
    }
  };

  const disableSearch = isLoading || (!value.trim() && selectedEmojis.length === 0);

  return (
    <div className="w-full max-w-full sm:max-w-4xl mx-auto px-2 sm:px-0">
      <div className="relative backdrop-blur-lg bg-white/5 border border-white/10 rounded-2xl p-4 sm:p-6 shadow-2xl">
        <div className="grid grid-cols-[auto,1fr] gap-3 sm:gap-4 items-start w-full">
          <div className="mt-1 sm:mt-3">
            <Sparkles className="w-6 h-6 text-purple-400" />
          </div>
          <div className="w-full">
            <Textarea
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe your mood first, then optionally genres or artists (add emojis if you want)"
              className="min-h-[100px] bg-transparent border-none resize-none text-white placeholder:text-gray-500 focus-visible:ring-0 focus-visible:ring-offset-0 p-0 text-left"
            />
            <div className="mt-4">
              <EmojiPicker value={selectedEmojis} onChange={onChangeEmojis} />
            </div>
            <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3 w-full sm:w-auto">
                <label htmlFor="song-limit" className="text-sm text-gray-400">
                  Number of songs:
                </label>
                <select
                  id="song-limit"
                  value={songLimit}
                  onChange={(e) => onChangeSongLimit(parseInt(e.target.value, 10))}
                  className="w-full sm:w-[7rem] px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 select-glass"
                  disabled={isLoading}
                >
                  {[10, 15, 20, 25, 30, 40, 50].map((val) => (
                    <option key={val} value={val} className="bg-gray-900 text-white">
                      {val}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3 w-full sm:w-auto">
                <label htmlFor="popularity" className="text-sm text-gray-400">
                  Popularity:
                </label>
                <select
                  id="popularity"
                  value={popularityLabel}
                  onChange={(e) => onChangePopularity(e.target.value)}
                  className="w-full sm:w-52 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 select-glass"
                  disabled={isLoading}
                >
                  {Object.keys(popularityRanges).map((label) => (
                    <option key={label} value={label} className="bg-gray-900 text-white">
                      {label}
                    </option>
                  ))}
                </select>
                <span className="text-xs text-gray-500">
                  {popularityRanges[popularityLabel]
                    ? `${popularityRanges[popularityLabel]?.[0]}–${popularityRanges[popularityLabel]?.[1]}`
                    : "no filter"}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center mt-4 pt-4 border-t border-white/10">
          <div className="flex items-center gap-2 text-gray-400 text-sm text-center sm:text-left justify-center sm:justify-start">
            <Search className="w-4 h-4" />
            <span className="text-sm">Mood-first music discovery (genres/artists respected)</span>
          </div>
          <Button
            onClick={onSearch}
            disabled={disableSearch}
            className="w-40 self-center sm:self-auto bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-4"
          >
            {isLoading ? (
              <>
                <span className="animate-pulse">{loadingLabel || "Searching..."}</span>
              </>
            ) : (
              "Find Mood Songs"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
