import React, { useState } from "react";
import { SearchInput } from "./components/SearchInput";
import { ResultsGrid } from "./components/ResultsGrid";
import { ApiService, Track } from "./services/api";

export default function App() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedEmojis, setSelectedEmojis] = useState<string[]>([]);
  const [songLimit, setSongLimit] = useState<number>(10);
  const [popularity, setPopularity] = useState<number>(1);
  const [lastSearch, setLastSearch] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRecommending, setIsRecommending] = useState(false);
  const [results, setResults] = useState<Track[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [rawResponse, setRawResponse] = useState<any | null>(null);
  const [analysis, setAnalysis] = useState<{ mood?: string | null; matched_criteria?: string[] | null } | null>(null);

  const isLoading = isAnalyzing || isRecommending;

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
    setLastSearch(hasQuery ? searchQuery : selectedEmojis.join(" "));

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
      const recommendResponse = await ApiService.recommendMusic({
        query: searchQuery,
        limit: songLimit,
        emojis: hasEmojis ? selectedEmojis : undefined,
        analysis: analysisResponse.analysis,
        popularity: popularity,
      });

      setRawResponse({ analysis: analysisResponse, recommend: recommendResponse });

      if (recommendResponse.success) {
        setResults(recommendResponse.songs);
        setAnalysis(recommendResponse.analysis || analysisResponse.analysis || {});
      } else {
        setError(recommendResponse.error || "Failed to get recommendations");
        setResults([]);
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
      {/* Background decorative elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-pink-500/20 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 px-6 py-12">
        {/* Header */}
        <div className="max-w-7xl mx-auto mb-12">
          <div className="text-center mb-8">
            <h1 className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent mb-2">
              Mood to Music
            </h1>
            <p className="text-gray-400">Describe your mood; mention genres or artists if you want</p>
          </div>
        </div>

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
          popularity={popularity}
          onChangePopularity={setPopularity}
        />

        {/* Analysis status */}
        {(isAnalyzing || analysis) && (
          <div className="w-full max-w-4xl mx-auto mt-6">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex items-start justify-between">
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

        {/* Results */}
        <ResultsGrid songs={results} searchQuery={lastSearch} />

        {/* Error state */}
        {error && (
          <div className="w-full max-w-4xl mx-auto mt-8">
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-center">
              <div className="text-red-400 mb-2">Oops, error</div>
              <p className="text-red-300">{error}</p>
            </div>
          </div>
        )}

        {/* Empty state */}
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

        {/* Gemini JSON output viewer */}
        {rawResponse && (
          <div className="w-full max-w-4xl mx-auto mt-10">
            <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                <span className="text-sm text-gray-300">Gemini JSON (raw API response)</span>
                <span className="text-xs text-gray-500">debug</span>
              </div>
              <pre className="p-4 text-xs text-gray-300 overflow-auto max-h-80 whitespace-pre-wrap">
{JSON.stringify(
  // Prefer gemini-specific suggestions if backend adds them later
  (rawResponse as any).ai_suggestions ?? (rawResponse as any).suggestions ?? rawResponse,
  null,
  2
)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
