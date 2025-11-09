import { SongCard } from "./SongCard";
import { Music } from "lucide-react";
import { Track } from "../services/api";

interface ResultsGridProps {
  songs: Track[];
  searchQuery?: string;
  analysis?: {
    mood?: string | null;
    matched_criteria?: string[] | null;
  };
}

export function ResultsGrid({ songs, searchQuery, analysis }: ResultsGridProps) {
  if (songs.length === 0) {
    return null;
  }

  return (
    <div className="w-full max-w-7xl mx-auto mt-12 animate-in fade-in duration-500">
      {searchQuery && (
        <div className="mb-6 flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Music className="w-5 h-5 text-purple-400" />
            <h2 className="text-white">
              Results for: <span className="text-gray-400">{searchQuery}</span>
            </h2>
          </div>
          {analysis?.mood && (
            <span className="ml-2 text-xs px-2 py-1 rounded-full bg-purple-500/20 text-white border border-purple-500/30">
              Mood: {analysis.mood}
            </span>
          )}
          {analysis?.matched_criteria?.length ? (
            <div className="flex items-center gap-2 ml-2 flex-wrap">
              {analysis.matched_criteria.map((c) => (
                <span key={c} className="text-xs px-2 py-1 rounded-full bg-white/5 text-white border border-white/10">
                  {c}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {songs.map((track) => (
          <SongCard key={track.id || `${track.title}-${track.artist}`} track={track} />
        ))}
      </div>
    </div>
  );
}
