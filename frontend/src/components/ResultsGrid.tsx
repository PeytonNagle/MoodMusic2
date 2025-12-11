import { SongCard } from "./SongCard";
import { Music } from "lucide-react";
import { Track } from "../services/api";

interface ResultsGridProps {
  songs: Track[];
  searchQuery?: string;
}

export function ResultsGrid({ songs, searchQuery }: ResultsGridProps) {
  if (songs.length === 0) {
    return null;
  }

  return (
    <div className="w-full max-w-7xl mx-auto mt-12 animate-in fade-in duration-700">
      {searchQuery && (
        <div className="mb-8 flex items-center gap-3 flex-wrap px-4 sm:px-0">
          <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur-sm">
            <Music className="w-5 h-5 text-indigo-400" />
            <div className="flex flex-col sm:flex-row sm:items-center sm:gap-2">
              <span className="text-sm text-gray-400">Results for:</span>
              <span className="font-semibold text-white">{searchQuery}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span>•</span>
            <span>{songs.length} {songs.length === 1 ? "track" : "tracks"} found</span>
          </div>
        </div>
      )}
      
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 px-4 sm:px-0">
        {songs.map((track, index) => (
          <div
            key={track.id || `${track.title}-${track.artist}-${index}`}
            className="animate-in fade-in slide-in-from-bottom-4"
            style={{ animationDelay: `${index * 50}ms`, animationFillMode: "backwards" }}
          >
            <SongCard track={track} />
          </div>
        ))}
      </div>
    </div>
  );
}
