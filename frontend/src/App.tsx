import React, { useEffect, useState } from "react";
import { Sparkles, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import { SearchInput } from "./components/SearchInput";
import { ResultsGrid } from "./components/ResultsGrid";
import { Modal } from "./components/Modal";
import { Button } from "./components/ui/button";
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
  const [showDebug, setShowDebug] = useState(false);

  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authDisplayName, setAuthDisplayName] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historyMessage, setHistoryMessage] = useState<string | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  const isLoading = isAnalyzing || isRecommending;

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
        setIsAuthModalOpen(false);
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
    setShowDebug(false);

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
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-900 to-black text-white">
      {/* Background Effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-[40rem] h-[40rem] bg-indigo-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDuration: "4s" }} />
        <div className="absolute bottom-0 left-0 w-[40rem] h-[40rem] bg-green-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDuration: "6s" }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[30rem] h-[30rem] bg-amber-500/5 rounded-full blur-3xl animate-pulse" style={{ animationDuration: "8s" }} />
      </div>

      {/* Header */}
      <header className="relative z-10 px-4 sm:px-6 pt-6 pb-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 border border-indigo-400/20">
              <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
              </svg>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-gray-400">Mood to</p>
              <p className="text-xl font-bold text-white leading-tight">Music</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {user ? (
              <>
                <div className="flex items-center gap-2 rounded-full bg-white/5 border border-white/10 px-4 py-2">
                  <div className="h-8 w-8 rounded-full bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center font-semibold text-white shadow-sm">
                    {(user.display_name || user.email || "?").charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm text-gray-100 hidden sm:inline">{user.display_name || user.email}</span>
                </div>
                <button
                  onClick={() => {
                    setUser(null);
                    setHistoryEntries([]);
                  }}
                  className="text-sm text-gray-400 hover:text-white transition"
                >
                  Log out
                </button>
              </>
            ) : (
              <Button
                onClick={() => setIsAuthModalOpen(true)}
                className="rounded-full border border-indigo-400/30 bg-gradient-to-r from-indigo-500 to-indigo-600 px-5 py-2 font-semibold text-white shadow-lg shadow-indigo-500/30 hover:from-indigo-600 hover:to-indigo-700 transition"
              >
                Log in / Sign up
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 px-4 sm:px-6 pb-12">
        {/* Hero Section */}
        <section className="max-w-3xl mx-auto text-center mt-12 mb-10 space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/5 border border-white/10 px-4 py-2 text-sm font-semibold text-indigo-200 shadow-lg shadow-indigo-500/10">
            <Sparkles className="w-4 h-4" />
            <span>AI-powered playlist generation</span>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white leading-tight">
            Match your music to your mood.
          </h1>
          <p className="text-gray-300 text-lg sm:text-xl max-w-2xl mx-auto">
            Describe the vibe — we'll build the playlist.
          </p>
        </section>

        {/* Search Input */}
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

        {/* Analysis Display */}
        {(isAnalyzing || analysis) && (
          <div className="w-full max-w-3xl mx-auto mt-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-white/5 border border-white/10 rounded-2xl p-5 backdrop-blur-sm">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="text-sm font-semibold text-gray-300 mb-2">Mood analysis</div>
                  {analysis ? (
                    <div className="flex flex-wrap items-center gap-2">
                      {analysis.mood && (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-500/20 text-indigo-200 border border-indigo-500/30 text-sm font-medium">
                          <Sparkles className="w-3.5 h-3.5" />
                          {analysis.mood}
                        </span>
                      )}
                      {analysis.matched_criteria?.map((c) => (
                        <span key={c} className="px-3 py-1.5 rounded-full bg-white/5 text-gray-300 border border-white/10 text-sm">
                          {c}
                        </span>
                      ))}
                      {!analysis.mood && !analysis.matched_criteria?.length && (
                        <span className="text-sm text-gray-400">No analysis details available</span>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-sm text-gray-400">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>Analyzing your request...</span>
                    </div>
                  )}
                </div>
                {!isAnalyzing && (
                  <div className="flex items-center gap-1.5 text-xs text-green-400">
                    <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
                    <span>Ready</span>
                  </div>
                )}
              </div>
              {isRecommending && (
                <div className="flex items-center gap-3 mt-4 pt-4 border-t border-white/10 text-sm text-gray-300">
                  <svg className="animate-spin h-5 w-5 text-indigo-400" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Fetching recommendations...</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Results Grid */}
        <ResultsGrid songs={results} searchQuery={lastSearch} />

        {/* Error Display */}
        {error && (
          <div className="w-full max-w-3xl mx-auto mt-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-6 backdrop-blur-sm">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-red-300 mb-1">Something went wrong</div>
                  <p className="text-red-200 text-sm">{error}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && results.length === 0 && !error && !isAnalyzing && (
          <div className="text-center mt-24 animate-in fade-in duration-700">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-white/5 border border-white/10 mb-6">
              <svg className="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-gray-200 mb-2">Start discovering music</h3>
            <p className="text-gray-400 max-w-md mx-auto">
              Describe the vibe, mood, or type of music you're looking for and let AI find the perfect tracks.
            </p>
          </div>
        )}

        {/* Debug JSON Toggle */}
        {rawResponse && (
          <div className="w-full max-w-3xl mx-auto mt-10">
            <button
              onClick={() => setShowDebug(!showDebug)}
              className="w-full flex items-center justify-between px-4 py-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition text-sm text-gray-300"
            >
              <span className="font-medium">Debug: API Response</span>
              {showDebug ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            {showDebug && (
              <div className="mt-2 overflow-hidden rounded-xl border border-white/10 bg-slate-950 animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="px-4 py-2 border-b border-white/10 flex items-center justify-between">
                  <span className="text-xs text-gray-400">JSON Response</span>
                  <span className="text-xs text-gray-500 font-mono">developer mode</span>
                </div>
                <pre className="p-4 text-xs text-gray-300 overflow-auto max-h-96 whitespace-pre-wrap font-mono">
                  {JSON.stringify(
                    (rawResponse as any).ai_suggestions ?? (rawResponse as any).suggestions ?? rawResponse,
                    null,
                    2
                  )}
                </pre>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Auth Modal */}
      <Modal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        title={authMode === "login" ? "Sign in" : "Register"}
        subtitle={authMode === "login" ? "Welcome back" : "Create account"}
      >
        <div className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm text-gray-300 mb-2">
              Email
            </label>
            <input
              id="email"
              type="email"
              placeholder="your@email.com"
              autoComplete="email"
              className="w-full rounded-xl bg-white/5 border border-white/20 px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/40 transition"
              value={authEmail}
              onChange={(e) => setAuthEmail(e.target.value)}
            />
          </div>
          
          <div>
            <label htmlFor="password" className="block text-sm text-gray-300 mb-2">
              Password
            </label>
            <input
              id="password"
              type="password"
              placeholder="••••••••"
              autoComplete={authMode === "login" ? "current-password" : "new-password"}
              className="w-full rounded-xl bg-white/5 border border-white/20 px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/40 transition"
              value={authPassword}
              onChange={(e) => setAuthPassword(e.target.value)}
            />
          </div>
          
          {authMode === "register" && (
            <div>
              <label htmlFor="displayName" className="block text-sm text-gray-300 mb-2">
                Display name <span className="text-gray-500">(optional)</span>
              </label>
              <input
                id="displayName"
                type="text"
                placeholder="How should we call you?"
                autoComplete="nickname"
                className="w-full rounded-xl bg-white/5 border border-white/20 px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/40 transition"
                value={authDisplayName}
                onChange={(e) => setAuthDisplayName(e.target.value)}
              />
            </div>
          )}

          <Button
            onClick={handleAuthSubmit}
            disabled={isAuthLoading || !authEmail || !authPassword}
            className="w-full mt-6 rounded-xl bg-gradient-to-r from-indigo-500 to-indigo-600 py-3 text-white font-semibold shadow-lg shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition hover:from-indigo-600 hover:to-indigo-700"
          >
            {isAuthLoading ? "Please wait..." : authMode === "login" ? "Log in" : "Register"}
          </Button>

          <button
            onClick={() => {
              setAuthMode(authMode === "login" ? "register" : "login");
              setAuthError(null);
            }}
            className="w-full text-sm text-gray-400 hover:text-white transition"
          >
            {authMode === "login" ? "Need an account? Register" : "Already have an account? Log in"}
          </button>

          {authError && (
            <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20">
              <p className="text-sm text-red-300 text-center">{authError}</p>
            </div>
          )}
        </div>
      </Modal>

      {/* History Modal */}
      <Modal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        title="History"
        subtitle="Your saved moods"
        maxWidth="2xl"
      >
        {!user ? (
          <div className="py-10 text-center text-gray-300">
            {historyMessage || "Please sign in to view your saved history."}
          </div>
        ) : isHistoryLoading ? (
          <div className="py-10 flex items-center justify-center gap-3 text-gray-300">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>Loading history...</span>
          </div>
        ) : historyEntries.length === 0 ? (
          <div className="py-10 text-center text-gray-400">
            No past requests yet. Run a search to start building history.
          </div>
        ) : (
          <div className="max-h-[60vh] overflow-y-auto space-y-3">
            {historyMessage && (
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-300 text-center mb-4">
                {historyMessage}
              </div>
            )}
            {historyEntries.map((entry) => (
              <button
                key={entry.id}
                type="button"
                onClick={() => handleHistorySelect(entry)}
                className="w-full text-left rounded-2xl border border-white/10 bg-white/5 px-5 py-4 hover:border-indigo-400/40 hover:bg-white/10 transition-all group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-semibold group-hover:text-indigo-300 transition-colors break-words">
                      {entry.lastSearchLabel}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(entry.timestamp).toLocaleString()}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                      {entry.emojis.length > 0 ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1">
                          {entry.emojis.join(" ")}
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-white/5 border border-white/10 px-2.5 py-1 text-gray-400">
                          Text mood
                        </span>
                      )}
                      <span className="text-gray-500">•</span>
                      <span className="text-gray-400">
                        {entry.results.length} song{entry.results.length === 1 ? "" : "s"}
                      </span>
                      <span className="text-gray-500">•</span>
                      <span className="text-gray-400">{entry.popularityLabel}</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
