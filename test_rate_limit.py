"""
Rate limit stress test for /api/recommend.
Usage: python test_rate_limit.py [--requests N] [--workers N] [--delay SECONDS]
"""

import argparse
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import GPUtil as GPUtil  # noqa: PLC0414
    HAS_GPUTIL = True
except ImportError:
    GPUtil = None  # type: ignore[assignment]
    HAS_GPUTIL = False

BASE_URL = "http://localhost:5000"
ENDPOINT = f"{BASE_URL}/api/recommend"

PAYLOAD = {
    "query": "happy upbeat summer vibes",
    "emojis": ["😊", "☀️"],
    "limit": 3,
}

print_lock = threading.Lock()


def sample_gpu():
    if not HAS_GPUTIL:
        return None, None
    gpus = GPUtil.getGPUs()
    if not gpus:
        return None, None
    return gpus[0].load * 100, gpus[0].memoryUsed


def send_request(i: int):
    start = time.monotonic()
    try:
        resp = requests.post(ENDPOINT, json=PAYLOAD, timeout=15)
        elapsed = time.monotonic() - start
        gpu_load, gpu_mem_mb = sample_gpu()

        gpu_str = f"  gpu={gpu_load:.1f}%  gpu_mem={gpu_mem_mb:.0f}MB" if gpu_load is not None else ""
        with print_lock:
            print(f"[{i:>3}] status={resp.status_code}  time={elapsed:.2f}s{gpu_str}")

        return {"i": i, "status": resp.status_code, "elapsed": elapsed,
                "gpu_load": gpu_load, "gpu_mem_mb": gpu_mem_mb}

    except requests.exceptions.ConnectionError:
        elapsed = time.monotonic() - start
        with print_lock:
            print(f"[{i:>3}] CONNECTION_ERROR after {elapsed:.2f}s")
        return {"i": i, "status": "CONNECTION_ERROR", "elapsed": elapsed}

    except requests.exceptions.Timeout:
        elapsed = time.monotonic() - start
        with print_lock:
            print(f"[{i:>3}] TIMEOUT after {elapsed:.2f}s")
        return {"i": i, "status": "TIMEOUT", "elapsed": elapsed}


def run(num_requests: int, workers: int, delay: float):
    if not HAS_GPUTIL:
        print("GPUtil not installed — GPU tracking disabled (pip install gputil)")

    print(f"Sending {num_requests} requests to {ENDPOINT} ({workers} concurrent workers, delay={delay}s)\n")

    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for i in range(1, num_requests + 1):
            futures[executor.submit(send_request, i)] = i
            if delay > 0 and i < num_requests:
                time.sleep(delay)

        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: r["i"])

    # Summary
    print("\n--- Summary ---")
    status_counts: dict = {}
    for r in results:
        key = str(r["status"])
        status_counts[key] = status_counts.get(key, 0) + 1

    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count} responses")

    times = [r["elapsed"] for r in results]
    print(f"  avg response time: {sum(times)/len(times):.2f}s")
    print(f"  min: {min(times):.2f}s  max: {max(times):.2f}s")

    gpu_samples = [r["gpu_load"] for r in results if r.get("gpu_load") is not None]
    if gpu_samples:
        print(f"  avg gpu: {sum(gpu_samples)/len(gpu_samples):.1f}%  peak: {max(gpu_samples):.1f}%")

    rate_limited = [r for r in results if r["status"] == 429]
    if rate_limited:
        print(f"\n  Rate limiting detected at request #{rate_limited[0]['i']}")
    else:
        print(f"\n  No rate limiting detected (no 429 responses)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rate limit stress test for /api/recommend")
    parser.add_argument("--requests", type=int, default=20, help="Number of requests to send (default: 20)")
    parser.add_argument("--workers", type=int, default=5, help="Number of concurrent workers (default: 5)")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay in seconds between spawning requests (default: 0)")
    args = parser.parse_args()

    run(args.requests, args.workers, args.delay)
