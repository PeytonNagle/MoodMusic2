import { ExternalLink, Music, Play } from "lucide-react";
import { Track } from "../services/api";
import { useState } from "react";

interface SongCardProps {
  track: Track;
}

export function SongCard({ track }: SongCardProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioError, setAudioError] = useState(false);

  const handlePlayPreview = () => {
    if (!track.preview_url || audioError) return;
    
    const audio = new Audio(track.preview_url);
    audio.volume = 0.5;
    
    audio.addEventListener("error", () => {
      setAudioError(true);
      setIsPlaying(false);
    });
    
    audio.addEventListener("ended", () => {
      setIsPlaying(false);
    });
    
    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      audio.play();
      setIsPlaying(true);
    }
  };

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm transition-all duration-300 hover:border-indigo-500/30 hover:bg-white/10 hover:shadow-xl hover:shadow-indigo-500/10">
      {/* Album Art */}
      <div className="relative aspect-square overflow-hidden bg-gradient-to-br from-indigo-900/20 to-slate-900/20">
        {track.album_art ? (
          <img
            src={track.album_art}
            alt={`${track.album} artwork`}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Music className="h-16 w-16 text-white/20" />
          </div>
        )}
        
        {/* Overlay on Hover */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        
        {/* Play Button */}
        {track.preview_url && !audioError && (
          <button
            onClick={handlePlayPreview}
            className="absolute left-1/2 top-1/2 flex h-14 w-14 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-indigo-500 text-white opacity-0 shadow-lg shadow-indigo-500/50 transition-all duration-300 hover:scale-110 hover:bg-indigo-600 group-hover:opacity-100"
            aria-label={isPlaying ? "Pause preview" : "Play preview"}
          >
            {isPlaying ? (
              <div className="flex gap-1">
                <div className="h-4 w-1 bg-white" />
                <div className="h-4 w-1 bg-white" />
              </div>
            ) : (
              <Play className="h-6 w-6 translate-x-0.5" fill="white" />
            )}
          </button>
        )}

        {/* Popularity Badge */}
        {typeof track.popularity === "number" && (
          <div className="absolute right-2 top-2 rounded-full bg-black/60 px-2.5 py-1 text-xs font-semibold text-white backdrop-blur-sm">
            {track.popularity}% popular
          </div>
        )}
      </div>

      {/* Track Info */}
      <div className="space-y-2 p-4">
        <div className="min-h-[3rem]">
          <h3 className="line-clamp-1 font-semibold text-white transition-colors group-hover:text-indigo-300">
            {track.title}
          </h3>
          <p className="line-clamp-1 text-sm text-gray-400">{track.artist}</p>
        </div>

        <div className="flex items-center justify-between text-xs text-gray-500">
          <span className="line-clamp-1">{track.album}</span>
          {track.release_year && <span>{track.release_year}</span>}
        </div>

        {/* Duration & Spotify Link */}
        <div className="flex items-center justify-between border-t border-white/5 pt-3">
          {track.duration_formatted && (
            <span className="text-xs text-gray-400">{track.duration_formatted}</span>
          )}
          
          {track.spotify_url && (
            <a
              href={track.spotify_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-green-400 transition-colors hover:text-green-300"
            >
              <span>Spotify</span>
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
