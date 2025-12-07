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
}

export function SearchInput({
  value,
  onChange,
  onSearch,
  isLoading,
  loadingLabel,
  selectedEmojis,
  onChangeEmojis,
}: SearchInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSearch();
    }
  };

  const disableSearch = isLoading || (!value.trim() && selectedEmojis.length === 0);

  return (
    <div className="w-full max-w-4xl mx-auto">
      <div className="relative backdrop-blur-lg bg-white/5 border border-white/10 rounded-2xl p-6 shadow-2xl">
        <div className="flex items-start gap-4">
          <div className="mt-3">
            <Sparkles className="w-6 h-6 text-purple-400" />
          </div>
          <div className="flex-1">
            <Textarea
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe your mood first, then optionally genres or artists (add emojis if you want)"
              className="min-h-[100px] bg-transparent border-none resize-none text-white placeholder:text-gray-500 focus-visible:ring-0 focus-visible:ring-offset-0 p-0"
            />
            <div className="mt-4">
              <EmojiPicker value={selectedEmojis} onChange={onChangeEmojis} />
            </div>
          </div>
        </div>
        <div className="flex justify-between items-center mt-4 pt-4 border-t border-white/10">
          <div className="flex items-center gap-2 text-gray-400">
            <Search className="w-4 h-4" />
            <span className="text-sm">Mood-first music discovery (genres/artists respected)</span>
          </div>
          <Button
            onClick={onSearch}
            disabled={disableSearch}
            className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-6"
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
