import React, { useEffect, useRef, useState } from "react";
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
  const SONG_LIMIT_OPTIONS = [5, 10, 15, 20, 25];
  const [isSongLimitMenuOpen, setIsSongLimitMenuOpen] = useState(false);
  const songLimitMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (songLimitMenuRef.current && !songLimitMenuRef.current.contains(event.target as Node)) {
        setIsSongLimitMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  useEffect(() => {
    if (isLoading) {
      setIsSongLimitMenuOpen(false);
    }
  }, [isLoading]);

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
            <div className="mt-4 flex flex-col gap-4">
              <div className="flex flex-col gap-2 w-full sm:w-auto sm:self-start">
                <label htmlFor="song-limit" className="text-sm text-gray-400">
                  Number of songs:
                </label>
                <div ref={songLimitMenuRef} className="relative inline-block">
                  <button
                    id="song-limit"
                    type="button"
                    onClick={() => setIsSongLimitMenuOpen((open) => !open)}
                    disabled={isLoading}
                    aria-haspopup="listbox"
                    aria-expanded={isSongLimitMenuOpen}
                    className="inline-flex w-auto min-w-[5rem] items-center justify-between gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-left text-sm font-medium text-white shadow-inner shadow-white/5 transition hover:border-purple-500/40 hover:bg-white/10"
                  >
                    <span>{songLimit} songs</span>
                    <svg
                      className={`w-3 h-3 transition-transform ${isSongLimitMenuOpen ? "rotate-180" : ""}`}
                      viewBox="0 0 12 12"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                  {isSongLimitMenuOpen && (
                    <div
                      className="absolute left-0 z-20 mt-2 w-full min-w-[8rem] overflow-hidden rounded-lg border border-white/10 shadow-2xl shadow-purple-900/20 sm:w-32"
                      style={{ backgroundColor: "#111827" }}
                      role="listbox"
                      aria-labelledby="song-limit"
                    >
                      {SONG_LIMIT_OPTIONS.map((option) => (
                        <button
                          key={option}
                          type="button"
                          onClick={() => {
                            onChangeSongLimit(option);
                            setIsSongLimitMenuOpen(false);
                          }}
                          role="option"
                          aria-selected={option === songLimit}
                          className={`flex w-full items-center justify-between px-3 py-2 text-sm transition ${
                            option === songLimit ? "bg-purple-500/40 text-white" : "text-white hover:bg-white/10"
                          }`}
                        >
                          <span>{option}</span>
                          <span className="text-xs uppercase tracking-wide">{option === songLimit ? "selected" : ""}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="mt-6 pt-4 border-t border-white/10">
          <div className="flex flex-col gap-2 w-full">
            <label htmlFor="popularity" className="text-sm text-gray-400">
              Popularity filter:
            </label>
            <div className="flex flex-col gap-2">
              <select
                id="popularity"
                value={popularityLabel}
                onChange={(e) => onChangePopularity(e.target.value)}
                className="w-full px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500/50 select-glass"
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
