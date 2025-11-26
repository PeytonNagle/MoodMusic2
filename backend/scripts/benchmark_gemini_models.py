import os
import sys
import time
import statistics
from typing import List, Tuple

# Ensure backend root is on sys.path whether running from repo root or backend/
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from config import Config  # ensures .env is loaded
from services.gemini_service import GeminiService


def generate_prompts(count: int = 10) -> List[str]:
    """Generate prompts that increase in complexity.

    Strategy: cycle through a few base moods and progressively add constraints
    (genres, artists, eras, activities, instruments, exclusions) as level grows.
    """
    base_moods = [
        "calm focus",
        "energetic gym",
        "nostalgic night drive",
        "melancholic reflection",
        "happy summer beach vibes",
    ]
    constraints_layers = [
        "",
        "lo-fi beats",
        "studying",
        "genre: indie rock / chillhop",
        "artist: Drake or similar",
        "era: 2000s–2010s",
        "instruments: piano, soft drums",
        "tempo: mid-tempo",
        "instrumental preferred",
        "avoid explicit lyrics",
    ]

    prompts: List[str] = []
    for i in range(1, count + 1):
        base = base_moods[(i - 1) % len(base_moods)]
        # Add first i constraints to increase complexity
        layers = [c for c in constraints_layers[:i] if c]
        details = ", ".join(layers)
        prompt = base if not details else f"{base} — {details}"
        prompts.append(prompt)
    return prompts


def run_benchmark(api_key: str, model: str, prompts: List[str], num_songs: int = 10) -> Tuple[List[float], List[bool]]:
    service = GeminiService(api_key)
    timings: List[float] = []
    successes: List[bool] = []

    print(f"\n=== Benchmarking model: {model} ===")
    for i, prompt in enumerate(prompts, start=1):
        print(f"[{model}] Prompt {i}/{len(prompts)} (complexity {i}): {prompt}")
        start = time.perf_counter()
        try:
            _ = service.get_song_suggestions(prompt, num_songs=num_songs, model=model)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            successes.append(True)
            print(f" -> Time: {elapsed:.2f}s (success)")
        except Exception as e:
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            successes.append(False)
            print(f" -> Time: {elapsed:.2f}s (error) {e}")

    return timings, successes


def main() -> None:
    api_key = Config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set. Add it to backend/.env or environment.")
        return

    models = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    prompts = generate_prompts(10)

    results = {}
    for m in models:
        timings, successes = run_benchmark(api_key, m, prompts, num_songs=10)
        # Only average successful runs
        successful_times = [t for t, ok in zip(timings, successes) if ok]
        avg = statistics.mean(successful_times) if successful_times else float("nan")
        results[m] = {
            "timings": timings,
            "successes": successes,
            "average_success": avg,
        }

    print("\n=== Summary ===")
    for m in models:
        timings = results[m]["timings"]
        successes = results[m]["successes"]
        avg = results[m]["average_success"]
        total = len(timings)
        ok = sum(1 for s in successes if s)
        print(f"Model: {m}")
        print(f"  Runs: {ok}/{total} succeeded")
        print(f"  Times: {[f'{t:.2f}s' for t in timings]}")
        print(f"  Average (successful only): {avg:.2f}s\n")


if __name__ == "__main__":
    main()
