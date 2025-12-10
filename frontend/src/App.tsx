import React, { useState } from "react";
import { SearchInput } from "./components/SearchInput";
import { ResultsGrid } from "./components/ResultsGrid";
import { ApiService, Track, User } from "./services/api";

export default function App() {
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

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedEmojis, setSelectedEmojis] = useState<string[]>([]);
  const [songLimit, setSongLimit] = useState<number>(10);
  const [popularityLabel, setPopularityLabel] =
    useState<PopularityLabel>("Any");
  const [lastSearch, setLastSearch] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRecommending, setIsRecommending] = useState(false);
  const [results, setResults] = useState<Track[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [rawResponse, setRawResponse] = useState<any | null>(null);
  const [analysis, setAnalysis] = useState<{
    mood?: string | null;
    matched_criteria?: string[] | null;
  } | null>(null);

  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authDisplayName, setAuthDisplayName] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(false);

  const isLoading = isAnalyzing || isRecommending;

  const handleAuthSubmit = async () => {
    setAuthError(null);
    setIsAuthLoading(true);
    try {
      const payload: {
        email: string;
        password: string;
        display_name?: string;
      } = {
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

  const handleSearch = async () => {
    const hasQuery = searchQuery.trim().length > 0;
    const hasEmojis = selectedEmojis.length > 0;
    if (!hasQuery && !hasEmojis) return;

    setIsAnalyzing(true);
    setIsRecommending(false);
    setError(null);
    setResults([]);
    setAnalysis(null);
    setRawResponse(null);
    setLastSearch(
      hasQuery ? searchQuery : selectedEmojis.join(" ")
    );

    try {
      const analysisResponse = await ApiService.analyzeMood({
        query: searchQuery,
        emojis: hasEmojis ? selectedEmojis : undefined,
      });

      setIsAnalyzing(false);
      setRawResponse({ analysis: analysisResponse });

      if (!analysisResponse.success) {
        setError(
          analysisResponse.error || "Failed to analyze mood"
        );
        return;
      }

      setAnalysis(analysisResponse.analysis || {});

      setIsRecommending(true);
      const selectedRange =
        POPULARITY_RANGES[popularityLabel];
      const popularityRange = selectedRange
        ? ([selectedRange[0], selectedRange[1]] as [
            number,
            number
          ])
        : undefined;
      const recommendResponse = await ApiService.recommendMusic(
        {
          query: searchQuery,
          limit: songLimit,
          emojis: hasEmojis ? selectedEmojis : undefined,
          analysis: analysisResponse.analysis,
          popularity_label:
            popularityLabel === "Any" ? undefined : popularityLabel,
          popularity_range: popularityRange,
          user_id: user?.id,
        }
      );

      setRawResponse({
        analysis: analysisResponse,
        recommend: recommendResponse,
      });

      if (recommendResponse.success) {
        setResults(recommendResponse.songs);
        setAnalysis(
          recommendResponse.analysis ||
            analysisResponse.analysis ||
            {}
        );
      } else {
        setError(
          recommendResponse.error ||
            "Failed to get recommendations"
        );
        setResults([]);
      }
    } catch (err: any) {
      console.error("Search error:", err);
      setError(
        "Failed to connect to the server. Please make sure the backend is running."
      );
      setResults([]);
      setRawResponse({
        success: false,
        error: "Network or server error",
      });
    } finally {
      setIsAnalyzing(false);
      setIsRecommending(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black">
      {/* BG Glow */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-pink-500/20 rounded-full blur-3xl" />
      </div>

      {/* ⭐ MOBILE SAFE WRAPPER ⭐ */}
      <div className="relative z-10 px-4 sm:px-6 py-8">
        <div className="max-w-lg sm:max-w-3xl mx-auto w-full">

          {/* ------ HEADER ------ */}
          <div className="text-center mb-8">
            <h1 className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent mb-2">
              Mood to Music
            </h1>
            <p className="text-gray-400">
              Describe your mood; mention genres or artists if you want
            </p>
          </div>

          {/* ------ ACCOUNT BOX ------ */}
          <div className="max-w-md mx-auto mb-10 bg-white/5 border border-white/10 rounded-2xl p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-sm text-gray-400 uppercase tracking-widest">
                  Account
                </p>
                <h2 className="text-xl font-semibold text-white">
                  {user
                    ? "Welcome back"
                    : authMode === "login"
                    ? "Log in"
                    : "Create an account"}
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
                      placeholder="Display name"
                      className="w-full rounded-xl bg-white/10 border border-white/20 px-4 py-2.5 text-white placeholder-gray-400 focus:outline-none focus:border-purple-400"
                      value={authDisplayName}
                      onChange={(e) =>
                        setAuthDisplayName(e.target.value)
                      }
                    />
                  )}
                </div>

                <button
                  onClick={handleAuthSubmit}
                  disabled={
                    isAuthLoading || !authEmail || !authPassword
                  }
                  className="w-full mt-4 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 py-2.5 text-white font-semibold shadow-lg shadow-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isAuthLoading
                    ? "Please wait…"
                    : authMode === "login"
                    ? "Log in"
                    : "Register"}
                </button>

                <button
                  onClick={() => {
                    setAuthMode(
                      authMode === "login" ? "register" : "login"
                    );
                    setAuthError(null);
                  }}
                  className="w-full mt-3 text-sm text-gray-400 hover:text-white transition"
                >
                  {authMode === "login"
                    ? "Need an account? Register"
                    : "Already have an account? Log in"}
                </button>

                {authError && (
                  <p className="text-sm text-red-400 mt-3 text-center">
                    {authError}
                  </p>
                )}
              </>
            )}

            {user && (
              <div className="mt-4 text-sm text-gray-300">
                Signed in as{" "}
                <span className="text-white font-medium">
                  {user.display_name || user.email}
                </span>
              </div>
            )}
          </div>

          {/* SEARCH INPUT */}
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            onSearch={handleSearch}
            isLoading={isLoading}
            loadingLabel={
              isAnalyzing
                ? "Analyzing..."
                : isRecommending
                ? "Finding songs..."
                : undefined
            }
            selectedEmojis={selectedEmojis}
            onChangeEmojis={setSelectedEmojis}
            songLimit={songLimit}
            onChangeSongLimit={setSongLimit}
            popularityRanges={POPULARITY_RANGES}
            popularityLabel={popularityLabel}
            onChangePopularity={setPopularityLabel}
          />

          {/* MOOD ANALYSIS */}
          {(isAnalyzing || analysis) && (
            <div className="w-full mx-auto mt-6">
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex items-start justify-between">
                <div>
                  <div className="text-sm text-gray-400 mb-1">
                    Mood analysis
                  </div>

                  {analysis ? (
                    <div className="flex flex-wrap items-center gap-2">
                      {analysis.mood && (
                        <span className="text-xs px-2 py-1 rounded-full bg-purple-500/20 text-white border border-purple-500/30">
                          Mood: {analysis.mood}
                        </span>
                      )}
                      {analysis.matched_criteria?.map((c) => (
                        <span
                          key={c}
                          className="text-xs px-2 py-1 rounded-full bg-white/5 text-white border border-white/10"
                        >
                          {c}
                        </span>
                      ))}

                      {!analysis.mood &&
                        !analysis.matched_criteria?.length && (
                          <span className="text-xs text-gray-400">
                            No analysis details returned
                          </span>
                        )}
                    </div>
                  ) : (
                    <div className="text-xs text-gray-400">
                      Analyzing your request...
                    </div>
                  )}
                </div>

                <div className="text-xs text-purple-300">
                  {isRecommending
                    ? "Finding songs..."
                    : isAnalyzing
                    ? "Analyzing..."
                    : "Analysis ready"}
                </div>
              </div>

              {isRecommending && (
                <div className="flex items-center gap-3 mt-3 text-base text-gray-400">
                  <span
                    className="spinner w-6 h-6"
                    aria-hidden="true"
                  />
                  <span className="text-gray-100">
                    Fetching recommendations...
                  </span>
                </div>
              )}
            </div>
          )}

          {/* RESULTS GRID */}
          <ResultsGrid songs={results} searchQuery={lastSearch} />

          {/* ERROR BOX */}
          {error && (
            <div className="w-full mx-auto mt-8">
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-center">
                <div className="text-red-400 mb-2">Oops, error</div>
                <p className="text-red-300">{error}</p>
              </div>
            </div>
          )}

          {/* EMPTY STATE */}
          {!isLoading &&
            results.length === 0 &&
            !error && (
              <div className="text-center mt-20">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-white/5 border border-white/10 mb-4">
                  <svg
                    className="w-8 h-8 text-gray-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                    />
                  </svg>
                </div>
                <h3 className="text-gray-400 mb-2">
                  Start discovering music
                </h3>
                <p className="text-gray-600">
                  Describe the vibe, mood, or type of music you're
                  looking for
                </p>
              </div>
            )}

          {/* RAW DEBUG */}
          {rawResponse && (
            <div className="w-full mx-auto mt-10">
              <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                  <span className="text-sm text-gray-300">
                    Gemini JSON (raw API response)
                  </span>
                  <span className="text-xs text-gray-500">debug</span>
                </div>
                <pre className="p-4 text-xs text-gray-300 overflow-auto max-h-80 whitespace-pre-wrap">
                  {JSON.stringify(
                    (rawResponse as any).ai_suggestions ??
                      (rawResponse as any).suggestions ??
                      rawResponse,
                    null,
                    2
                  )}
                </pre>
              </div>
            </div>
          )}

        </div> {/* end max-width container */}
      </div> {/* end padding wrapper */}
    </div>
  );
}
