import React, { useEffect, useRef, useState } from "react";
import { Clock, MoreHorizontal, Search, Sparkles } from "lucide-react";
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
  onOpenHistory: () => void;
  historyCount: number;
}

const SONG_LIMIT_OPTIONS = [5, 10, 15, 20, 25];

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
  onOpenHistory,
  historyCount,
}: SearchInputProps) {
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
  const popularityRange = popularityRanges[popularityLabel];

  return (
    <div className="w-full max-w-4xl mx-auto px-3 sm:px-0">
      <div className="relative overflow-hidden rounded-[26px] backdrop-blur-xl bg-[#0f162a]/80 border border-white/10 shadow-2xl shadow-black/30">
        <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-5">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-gray-300">Tell us the mood</p>
              <h3 className="text-lg font-semibold text-white leading-tight">Find songs by vibe</h3>
            </div>
          </div>
          <button
            type="button"
            onClick={onOpenHistory}
            className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-semibold text-gray-100 transition hover:border-indigo-400/60 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
          >
            <Clock className="w-3.5 h-3.5 text-indigo-200" />
            <span>History{historyCount > 0 ? ` (${historyCount})` : ""}</span>
          </button>
        </div>

        <div className="px-5 pb-6 space-y-6">
          <div className="pt-2">
            <Textarea
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe your mood, genre, or artists (emojis welcome)"
              className="min-h-[96px] bg-white/5 border border-white/10 rounded-2xl text-white placeholder:text-gray-400 focus-visible:ring-2 focus-visible:ring-indigo-500/40 focus-visible:ring-offset-0"
            />
          </div>

          <div className="space-y-4">
            <EmojiPicker value={selectedEmojis} onChange={onChangeEmojis} />

            <div className="grid grid-cols-2 sm:grid-cols-1 gap-2">
              <div className="flex flex-col gap-2 w-full sm:w-auto sm:self-start" ref={songLimitMenuRef}>
                <label htmlFor="song-limit" className="text-sm text-gray-200">
                  Number of songs
                </label>
                <div className="relative inline-block w-full sm:w-auto">
                  <button
                    id="song-limit"
                    type="button"
                    onClick={() => setIsSongLimitMenuOpen((open) => !open)}
                    disabled={isLoading}
                    aria-haspopup="listbox"
                    aria-expanded={isSongLimitMenuOpen}
                    className="inline-flex w-full sm:w-auto items-center justify-between gap-2 rounded-xl border border-white/15 bg-white/5 px-3 py-2.5 text-left text-sm font-medium text-white shadow-inner shadow-white/5 transition hover:border-indigo-500/50 hover:bg-white/10"
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
                      className="absolute left-0 z-20 mt-2 w-full min-w-[8rem] overflow-hidden rounded-xl border border-white/15 shadow-2xl shadow-indigo-900/20 sm:w-36 bg-slate-900/95"
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
                            option === songLimit ? "bg-indigo-500/40 text-white" : "text-white hover:bg-white/10"
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

              <div className="flex flex-col gap-2">
                <label htmlFor="popularity" className="text-sm text-gray-200">
                  Popularity filter
                </label>
                <div className="relative">
                  <select
                    id="popularity"
                    value={popularityLabel}
                    onChange={(e) => onChangePopularity(e.target.value)}
                    className="w-full appearance-none px-3 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 pr-10"
                    disabled={isLoading}
                  >
                    {Object.keys(popularityRanges).map((label) => (
                      <option key={label} value={label} className="bg-gray-900 text-white">
                        {label}
                      </option>
                    ))}
                  </select>
                  <MoreHorizontal className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                </div>
                <span className="text-xs text-gray-400">
                  {popularityRange ? `${popularityRange[0]}-${popularityRange[1]}` : "No filter applied"}
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3 pt-4 border-t border-white/10">
            <div className="flex justify-center w-full">
              <Button
                onClick={onSearch}
                disabled={disableSearch}
                className="w-full sm:w-2/3 lg:w-1/2 bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 text-white px-6 py-4 text-base font-semibold shadow-lg shadow-indigo-500/30"
              >
                {isLoading ? (
                  <span className="animate-pulse">{loadingLabel || "Searching..."}</span>
                ) : (
                  "Generate playlist"
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
