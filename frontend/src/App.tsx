import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { SearchInput } from "./components/SearchInput";
import { ResultsGrid } from "./components/ResultsGrid";
import { ApiService, Track, User, RecommendResponse, HistoryItemResponse } from "./services/api";

const POPULARITY_RANGES = {
  Any: null,
  "Global / Superstar": [90, 100],
  "Hot / Established": [75, 89],
  "Buzzing / Moderate": [50, 74],
  Growing: [25, 49],
  Rising: [15, 24],
  "Under the Radar": [0, 14],
} as const;

type PopularityLabel = keyof typeof POPULARITY_RANGES;
type AnalysisData = { mood?: string | null; matched_criteria?: string[] | null } | null;

const buildTrackKey = (track: Track): string | null => {
  if (!track) return null;
  if (track.id) return `id:${track.id}`;
  const title = (track.title || "").trim().toLowerCase();
  const artist = (track.artist || "").trim().toLowerCase();
  if (!title && !artist) return null;
  return `${title}|${artist}`;
};

const mergeUniqueTracks = (target: Track[], incoming: Track[], seen: Set<string>): Track[] => {
  for (const track of incoming || []) {
    const key = buildTrackKey(track);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    target.push(track);
  }
  return target;
};

const normalizePopularityLabel = (value: string | null | undefined): PopularityLabel => {
  if (typeof value === "string" && value in POPULARITY_RANGES) {
    return value as PopularityLabel;
  }
  return "Any";
};

interface HistoryEntry {
  id: string;
  timestamp: number;
  inputQuery: string;
  emojis: string[];
  songLimit: number;
  popularityLabel: PopularityLabel;
  results: Track[];
  analysis: AnalysisData;
  lastSearchLabel: string;
}

export default function App() {

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedEmojis, setSelectedEmojis] = useState<string[]>([]);
  const [songLimit, setSongLimit] = useState<number>(10);
  const [popularityLabel, setPopularityLabel] = useState<PopularityLabel>("Any");
  const [lastSearch, setLastSearch] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRecommending, setIsRecommending] = useState(false);
  const [results, setResults] = useState<Track[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [rawResponse, setRawResponse] = useState<any | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisData>(null);

  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authDisplayName, setAuthDisplayName] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historyMessage, setHistoryMessage] = useState<string | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  const isLoading = isAnalyzing || isRecommending;
  const historyPortalTarget = typeof document !== "undefined" ? document.body : null;

  const mapHistoryItem = (item: HistoryItemResponse): HistoryEntry => {
    const createdTimestamp = item.created_at ? Date.parse(item.created_at) : Date.now();
    const songs: Track[] = (item.songs || []).map((song) => ({
      id: song.spotify_track_id || null,
      title: song.title || "Unknown title",
      artist: song.artist || "Unknown artist",
      album: song.album || "Unknown album",
      album_art: song.album_art || null,
      preview_url: song.preview_url || null,
      spotify_url: song.spotify_url || null,
      release_year: song.release_year || null,
      duration_formatted: song.duration_formatted || null,
      popularity: typeof song.popularity === "number" ? song.popularity : 0,
    }));

    const emojis = Array.isArray(item.emojis) ? item.emojis : [];
    const label = normalizePopularityLabel(item.popularity_label);
    const analysisData = item.analysis && typeof item.analysis === "object" ? item.analysis : null;

    return {
      id: `req-${item.request_id}`,
      timestamp: createdTimestamp,
      inputQuery: item.text_description || "",
      emojis,
      songLimit: item.num_songs_requested || 10,
      popularityLabel: label,
      results: songs,
      analysis: analysisData,
      lastSearchLabel: item.text_description || (emojis.join(" ") || "Mood search"),
    };
  };

  const loadHistory = async (userId: number) => {
    setIsHistoryLoading(true);
    setHistoryMessage(null);
    try {
      const response = await ApiService.getUserHistory(userId, 20);
      if (response.success) {
        const mapped = response.history.map((entry) => mapHistoryItem(entry));
        setHistoryEntries(mapped);
      } else {
        setHistoryMessage(response.error || "Unable to load history.");
      }
    } catch (err) {
      console.error("History load error:", err);
      setHistoryMessage("Unable to load history. Please try again.");
    } finally {
      setIsHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (!user) {
      setHistoryEntries([]);
      setHistoryMessage(null);
      return;
    }
    loadHistory(user.id);
  }, [user]);

  const handleAuthSubmit = async () => {
    setAuthError(null);
    setIsAuthLoading(true);
    try {
      const payload: { email: string; password: string; display_name?: string } = {
        email: authEmail.trim().toLowerCase(),
        password: authPassword,
      };
      if (authMode === "register" && authDisplayName.trim()) {
        payload.display_name = authDisplayName.trim();
      }

      const response =
        authMode === "login"
          ? await ApiService.loginUser(payload)
          : await ApiService.registerUser(payload);

      if (response.success && response.user) {
        setUser(response.user);
        setAuthEmail("");
        setAuthPassword("");
        setAuthDisplayName("");
      } else {
        setAuthError(response.error || "Unable to complete request");
      }
    } catch (err) {
      console.error("Auth error:", err);
      setAuthError("Unexpected error. Please try again.");
    } finally {
      setIsAuthLoading(false);
    }
  };

  const handleOpenHistory = () => {
    if (!user) {
      setHistoryMessage("Sign in to view your personal history.");
      setIsHistoryOpen(true);
      return;
    }
    if (!historyEntries.length && !isHistoryLoading) {
      loadHistory(user.id);
    }
    setHistoryMessage(null);
    setIsHistoryOpen(true);
  };

  const handleHistorySelect = (entry: HistoryEntry) => {
    if (!user) {
      setHistoryMessage("Please sign in to load saved history.");
      setIsHistoryOpen(true);
      return;
    }
    setSearchQuery(entry.inputQuery);
    setSelectedEmojis(entry.emojis);
    setSongLimit(entry.songLimit);
    setPopularityLabel(entry.popularityLabel);
    setResults(entry.results);
    setAnalysis(entry.analysis);
    setLastSearch(entry.lastSearchLabel);
    setError(null);
    setRawResponse(null);
    setIsAnalyzing(false);
    setIsRecommending(false);
    setIsHistoryOpen(false);
  };

  const handleSearch = async () => {
    const trimmedQuery = searchQuery.trim();
    const hasQuery = trimmedQuery.length > 0;
    const hasEmojis = selectedEmojis.length > 0;
    if (!hasQuery && !hasEmojis) return;

    const snapshot = {
      inputQuery: searchQuery,
      emojis: [...selectedEmojis],
      songLimit,
      popularityLabel,
      lastSearchLabel: (hasQuery ? trimmedQuery : selectedEmojis.join(" ")) || "Mood search",
    };

    setIsAnalyzing(true);
    setIsRecommending(false);
    setError(null);
    setResults([]);
    setAnalysis(null);
    setRawResponse(null);
    setLastSearch(snapshot.lastSearchLabel);

    try {
      const analysisResponse = await ApiService.analyzeMood({
        query: searchQuery,
        emojis: hasEmojis ? selectedEmojis : undefined,
      });

      setIsAnalyzing(false);
      setRawResponse({ analysis: analysisResponse });

      if (!analysisResponse.success) {
        setError(analysisResponse.error || "Failed to analyze mood");
        return;
      }

      setAnalysis(analysisResponse.analysis || {});

      setIsRecommending(true);
      const selectedRange = POPULARITY_RANGES[popularityLabel];
      const popularityRange = selectedRange ? [selectedRange[0], selectedRange[1]] as [number, number] : undefined;
      const recommendBasePayload = {
        query: searchQuery,
        emojis: hasEmojis ? selectedEmojis : undefined,
        analysis: analysisResponse.analysis,
        popularity_label: popularityLabel === "Any" ? undefined : popularityLabel,
        popularity_range: popularityRange,
        user_id: user?.id,
      };

      const aggregatedSongs: Track[] = [];
      const seenTrackKeys = new Set<string>();
      const clientMaxAttempts = 3;
      let clientAttempt = 0;
      let latestAnalysisData = analysisResponse.analysis || {};
      let lastRecommendResponse: RecommendResponse | null = null;

      while (clientAttempt < clientMaxAttempts && aggregatedSongs.length < songLimit) {
        clientAttempt += 1;
        const remainingNeeded = songLimit - aggregatedSongs.length;
        const requestLimit = Math.max(remainingNeeded, 10);
        const recommendResponse = await ApiService.recommendMusic({
            ...recommendBasePayload,
            limit: requestLimit,
        });
        lastRecommendResponse = recommendResponse;

        if (!recommendResponse.success) {
          setRawResponse({ analysis: analysisResponse, recommend: recommendResponse });
          setError(recommendResponse.error || "Failed to get recommendations");
          setResults([]);
          return;
        }

        latestAnalysisData = recommendResponse.analysis || latestAnalysisData;
        mergeUniqueTracks(aggregatedSongs, recommendResponse.songs, seenTrackKeys);
        if (aggregatedSongs.length >= songLimit) {
          break;
        }
      }

      setRawResponse({ analysis: analysisResponse, recommend: lastRecommendResponse });

      if (!lastRecommendResponse || !lastRecommendResponse.success) {
        setError("Failed to get recommendations");
        setResults([]);
        return;
      }

      const finalSongs = aggregatedSongs.slice(0, songLimit);

      if (finalSongs.length === 0) {
        setError("No songs found for this request. Try adjusting your mood or filters.");
        setResults([]);
        return;
      }

      setResults(finalSongs);
      const finalAnalysis = latestAnalysisData || analysisResponse.analysis || {};
      setAnalysis(finalAnalysis);
      if (finalSongs.length < songLimit) {
        setError(`Only found ${finalSongs.length} songs for this request. Try broadening your filters.`);
      }

      if (user?.id && finalSongs.length > 0) {
        const historyEntry: HistoryEntry = {
          id: `temp-${Date.now()}`,
          timestamp: Date.now(),
          inputQuery: snapshot.inputQuery,
          emojis: snapshot.emojis,
          songLimit: snapshot.songLimit,
          popularityLabel: snapshot.popularityLabel,
          results: finalSongs,
          analysis: finalAnalysis,
          lastSearchLabel: snapshot.lastSearchLabel,
        };
        setHistoryEntries((prev) => {
          const filtered = prev.filter((entry) => entry.lastSearchLabel !== historyEntry.lastSearchLabel);
          return [historyEntry, ...filtered].slice(0, 20);
        });
      }
    } catch (err: any) {
      console.error("Search error:", err);
      setError("Failed to connect to the server. Please make sure the backend is running.");
      setResults([]);
      setRawResponse({ success: false, error: "Network or server error" });
    } finally {
      setIsAnalyzing(false);
      setIsRecommending(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black">
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-pink-500/20 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 px-6 py-12">
        <div className="max-w-7xl mx-auto mb-12">
          <div className="text-center mb-8">
            <h1 className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent mb-2">
              Mood to Music
            </h1>
            <p className="text-gray-400">Describe your mood; mention genres or artists if you want</p>
          </div>
        </div>

        <div className="max-w-md mx-auto mb-10 bg-white/5 border border-white/10 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm text-gray-400 uppercase tracking-widest">Account</p>
              <h2 className="text-xl font-semibold text-white">
                {user ? "Welcome back" : authMode === "login" ? "Log in" : "Create an account"}
              </h2>
            </div>
            {user && (
              <button
                onClick={() => setUser(null)}
                className="text-sm text-purple-300 hover:text-purple-100 transition"
              >
                Log out
              </button>
            )}
          </div>

          {!user && (
            <>
              <div className="space-y-3">
                <input
                  type="email"
                  placeholder="Email"
                  className="w-full rounded-xl bg-white/10 border border-white/20 px-4 py-2.5 text-white placeholder-gray-400 focus:outline-none focus:border-purple-400"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                />
                <input
                  type="password"
                  placeholder="Password"
                  className="w-full rounded-xl bg-white/10 border border-white/20 px-4 py-2.5 text-white placeholder-gray-400 focus:outline-none focus:border-purple-400"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                />
                {authMode === "register" && (
                  <input
                    type="text"
                    placeholder="Display name (optional)"
                    className="w-full rounded-xl bg-white/10 border border-white/20 px-4 py-2.5 text-white placeholder-gray-400 focus:outline-none focus:border-purple-400"
                    value={authDisplayName}
                    onChange={(e) => setAuthDisplayName(e.target.value)}
                  />
                )}
              </div>

              <button
                onClick={handleAuthSubmit}
                disabled={isAuthLoading || !authEmail || !authPassword}
                className="w-full mt-4 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 py-2.5 text-white font-semibold shadow-lg shadow-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isAuthLoading ? "Please wait…" : authMode === "login" ? "Log in" : "Register"}
              </button>

              <button
                onClick={() => {
                  setAuthMode(authMode === "login" ? "register" : "login");
                  setAuthError(null);
                }}
                className="w-full mt-3 text-sm text-gray-400 hover:text-white transition"
              >
                {authMode === "login" ? "Need an account? Register" : "Already have an account? Log in"}
              </button>

              {authError && <p className="text-sm text-red-400 mt-3 text-center">{authError}</p>}
            </>
          )}

          {user && (
            <div className="mt-4 text-sm text-gray-300">
              Signed in as <span className="text-white font-medium">{user.display_name || user.email}</span>
            </div>
          )}
        </div>

        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          onSearch={handleSearch}
          isLoading={isLoading}
          loadingLabel={isAnalyzing ? "Analyzing..." : isRecommending ? "Finding songs..." : undefined}
          selectedEmojis={selectedEmojis}
          onChangeEmojis={setSelectedEmojis}
          songLimit={songLimit}
          onChangeSongLimit={setSongLimit}
          popularityRanges={POPULARITY_RANGES}
          popularityLabel={popularityLabel}
          onChangePopularity={setPopularityLabel}
          onOpenHistory={handleOpenHistory}
          historyCount={user ? historyEntries.length : 0}
        />

        {(isAnalyzing || analysis) && (
          <div className="w-full max-w-4xl mx-auto mt-6">
            <div className="bg-white/5 border border白/10 rounded-xl p-4 flex items-start justify-between">
              <div>
                <div className="text-sm text-gray-400 mb-1">Mood analysis</div>
                {analysis ? (
                  <div className="flex flex-wrap items-center gap-2">
                    {analysis.mood && (
                      <span className="text-xs px-2 py-1 rounded-full bg-purple-500/20 text-white border border-purple-500/30">
                        Mood: {analysis.mood}
                      </span>
                    )}
                    {analysis.matched_criteria?.map((c) => (
                      <span key={c} className="text-xs px-2 py-1 rounded-full bg-white/5 text-white border border-white/10">
                        {c}
                      </span>
                    ))}
                    {!analysis.mood && !analysis.matched_criteria?.length && (
                      <span className="text-xs text-gray-400">No analysis details returned</span>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-gray-400">Analyzing your request...</div>
                )}
              </div>
              <div className="text-xs text-purple-300">
                {isRecommending ? "Finding songs..." : isAnalyzing ? "Analyzing..." : "Analysis ready"}
              </div>
            </div>
            {isRecommending && (
              <div className="flex items-center gap-3 mt-3 text-base text-gray-400">
                <span className="spinner w-6 h-6" aria-hidden="true" />
                <span className="text-gray-100">Fetching recommendations...</span>
              </div>
            )}
          </div>
        )}

        <ResultsGrid songs={results} searchQuery={lastSearch} />

        {error && (
          <div className="w-full max-w-4xl mx-auto mt-8">
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-center">
              <div className="text-red-400 mb-2">Oops, error</div>
              <p className="text-red-300">{error}</p>
            </div>
          </div>
        )}

        {!isLoading && results.length === 0 && !error && (
          <div className="text-center mt-20">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-white/5 border border-white/10 mb-4">
              <svg className="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                />
              </svg>
            </div>
            <h3 className="text-gray-400 mb-2">Start discovering music</h3>
            <p className="text-gray-600">Describe the vibe, mood, or type of music you're looking for</p>
          </div>
        )}

        {rawResponse && (
          <div className="w-full max-w-4xl mx-auto mt-10">
            <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                <span className="text-sm text-gray-300">Gemini JSON (raw API response)</span>
                <span className="text-xs text-gray-500">debug</span>
              </div>
              <pre className="p-4 text-xs text-gray-300 overflow-auto max-h-80 whitespace-pre-wrap">
                {JSON.stringify(
                  (rawResponse as any).ai_suggestions ?? (rawResponse as any).suggestions ?? rawResponse,
                  null,
                  2
                )}
              </pre>
            </div>
          </div>
        )}
      </div>
      {historyPortalTarget &&
        isHistoryOpen &&
        createPortal(
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 9999,
              backgroundColor: "rgba(15, 15, 30, 0.85)",
              backdropFilter: "blur(6px)",
              WebkitBackdropFilter: "blur(6px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "1.5rem",
            }}
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setIsHistoryOpen(false);
              }
            }}
          >
            <div className="w-full max-w-2xl rounded-2xl border border-white/20 bg-[#151529] shadow-2xl shadow-purple-900/40">
              <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-gray-400">Your saved moods</p>
                  <h3 className="text-xl text-white font-semibold">History</h3>
                </div>
                <button
                  onClick={() => setIsHistoryOpen(false)}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/30 text-white hover:border-white hover:bg-white/10 transition"
                  aria-label="Close history"
                >
                  <span className="text-lg leading-none text-white">&times;</span>
                </button>
              </div>
              {!user ? (
                <div className="px-6 py-10 text-center text-gray-300">
                  {historyMessage || "Please sign in to view your saved history."}
                </div>
              ) : isHistoryLoading ? (
                <div className="px-6 py-10 text-center text-gray-300">Loading history…</div>
              ) : historyEntries.length === 0 ? (
                <div className="px-6 py-10 text-center text-gray-400">
                  No past requests yet. Run a search to start building history.
                </div>
              ) : (
                <div className="max-h-[60vh] overflow-y-auto space-y-4 px-5 py-4">
                  {historyMessage && (
                    <div className="text-center text-xs text-red-300 mb-2">{historyMessage}</div>
                  )}
                  {historyEntries.map((entry) => (
                    <button
                      key={entry.id}
                      type="button"
                      onClick={() => handleHistorySelect(entry)}
                      className="w-full text-left rounded-2xl border border-white/10 bg-white/5 px-5 py-4 hover:border-purple-400/40 hover:bg-white/10 transition flex items-center justify-between gap-4 shadow-inner shadow-black/20"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-white font-semibold break-words">{entry.lastSearchLabel}</p>
                        <p className="text-xs text-gray-400">{new Date(entry.timestamp).toLocaleString()}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-400">
                          {entry.emojis.length > 0 ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-2 py-0.5">{entry.emojis.join(" ")}</span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full bg-white/5 px-2 py-0.5">Text mood</span>
                          )}
                          <span className="text-gray-500">•</span>
                          <span>{entry.results.length} song{entry.results.length === 1 ? "" : "s"}</span>
                          <span className="text-gray-500">•</span>
                          <span>{entry.songLimit} requested</span>
                        </div>
                      </div>
                      <span className="text-sm font-semibold text-purple-200">Load</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>,
          historyPortalTarget,
        )}
    </div>
  );
}
