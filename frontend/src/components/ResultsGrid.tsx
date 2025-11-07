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
    <div className="w-full max-w-7xl mx-auto mt-12 animate-in fade-in duration-500">
      {searchQuery && (
        <div className="mb-6 flex items-center gap-3">
          <Music className="w-5 h-5 text-purple-400" />
          <h2 className="text-white">
            Results for: <span className="text-gray-400">{searchQuery}</span>
          </h2>
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
