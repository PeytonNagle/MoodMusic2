import { ExternalLink, Play, Pause } from "lucide-react";
import { ImageWithFallback } from "./figma/ImageWithFallback";
import { useState } from "react";
import { Track } from "../services/api";

interface SongCardProps {
  track: Track;
}

export function SongCard({ track }: SongCardProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [audio] = useState(() => track.preview_url ? new Audio(track.preview_url) : null);

  const togglePlay = () => {
    if (!audio) return;
    
    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      audio.play();
      setIsPlaying(true);
      audio.onended = () => setIsPlaying(false);
    }
  };

  return (
    <div className="group relative backdrop-blur-md bg-white/5 border border-white/10 rounded-xl p-4 hover:bg-white/10 transition-all duration-300 hover:border-purple-500/30 hover:shadow-lg hover:shadow-purple-500/10">
      <div className="relative mb-4">
        <div className="aspect-square rounded-lg overflow-hidden bg-gray-800">
          <ImageWithFallback
            src={track.album_art || ''}
            alt={`${track.album} cover`}
            className="w-full h-full object-cover"
          />
        </div>
        {track.preview_url && (
          <button
            onClick={togglePlay}
            className="absolute top-2 right-2 w-10 h-10 rounded-full bg-purple-500 hover:bg-purple-600 flex items-center justify-center transition-all duration-200 opacity-0 group-hover:opacity-100 shadow-lg"
          >
            {isPlaying ? (
              <Pause className="w-5 h-5 text-white fill-white" />
            ) : (
              <Play className="w-5 h-5 text-white fill-white ml-0.5" />
            )}
          </button>
        )}
      </div>
      
      <div className="space-y-2">
        <h3 className="text-white line-clamp-1">{track.title}</h3>
        <p className="text-gray-400 line-clamp-1">{track.artist}</p>
        <p className="text-gray-500 line-clamp-1">{track.album}</p>
        
        <div className="flex items-center justify-between pt-2">
          <div className="text-xs text-gray-500">
            {track.release_year && <span>{track.release_year}</span>}
            {track.release_year && track.duration_formatted && <span className="mx-1">•</span>}
            {track.duration_formatted && <span>{track.duration_formatted}</span>}
          </div>
          {track.spotify_url && (
            <a
              href={track.spotify_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 transition-colors"
            >
              <span>Open in Spotify</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
