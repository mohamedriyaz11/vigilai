#!/usr/bin/env python3
"""Detector inference benchmark for VigilAI.

Measures actual YOLOv8n inference latency and throughput (FPS) at 320x320 px.
Prints measured statistics without any hardcoded or fabricated numbers.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np

from perception.detector import ObjectDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark_detector")


def run_benchmark(
    weights: str = "yolov8n.pt",
    input_size: int = 320,
    iterations: int = 50,
    warmup: int = 10,
    output_json: str | None = None,
) -> dict[str, float]:
    """Execute live timing benchmark on the object detector."""
    logger.info("Initializing detector with weights '%s' at %d px...", weights, input_size)
    detector = ObjectDetector(model_name_or_path=weights, input_size=input_size)

    # Synthetic test frame (simulates camera input in volatile RAM)
    dummy_frame = np.random.randint(0, 256, (input_size, input_size, 3), dtype=np.uint8)

    logger.info("Warming up with %d runs...", warmup)
    for _ in range(warmup):
        detector.detect(dummy_frame)

    logger.info("Running %d timed inference iterations...", iterations)
    latencies_ms: list[float] = []

    for _ in range(iterations):
        t0 = time.perf_counter()
        detector.detect(dummy_frame)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    latencies_ms.sort()
    mean_ms = float(np.mean(latencies_ms))
    p50_ms = float(np.percentile(latencies_ms, 50))
    p95_ms = float(np.percentile(latencies_ms, 95))
    min_ms = float(np.min(latencies_ms))
    max_ms = float(np.max(latencies_ms))
    fps = 1000.0 / mean_ms if mean_ms > 0 else 0.0

    print("\n" + "=" * 50)
    print(" VIGILAI DETECTOR BENCHMARK RESULTS (MEASURED)")
    print("=" * 50)
    print(f" Model Weights      : {weights}")
    print(f" Input Resolution   : {input_size} x {input_size} px")
    print(f" Iterations Evaluated: {iterations}")
    print(f" Mean Latency       : {mean_ms:.2f} ms")
    print(f" Median (p50)       : {p50_ms:.2f} ms")
    print(f" 95th Percentile    : {p95_ms:.2f} ms")
    print(f" Min Latency        : {min_ms:.2f} ms")
    print(f" Max Latency        : {max_ms:.2f} ms")
    print(f" Throughput (FPS)   : {fps:.2f} FPS")
    print("=" * 50 + "\n")

    results = {
        "weights": weights,
        "input_size": input_size,
        "iterations": iterations,
        "mean_latency_ms": round(mean_ms, 2),
        "p50_latency_ms": round(p50_ms, 2),
        "p95_latency_ms": round(p95_ms, 2),
        "min_latency_ms": round(min_ms, 2),
        "max_latency_ms": round(max_ms, 2),
        "fps": round(fps, 2),
    }

    if output_json:
        out_p = Path(output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        logger.info("Saved benchmark metrics to %s", output_json)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark YOLOv8n detector inference FPS.")
    parser.add_argument("--weights", default="yolov8n.pt", help="Path or name of model weights")
    parser.add_argument("--size", type=int, default=320, help="Inference resolution (default: 320)")
    parser.add_argument("--iterations", type=int, default=50, help="Number of benchmark iterations")
    parser.add_argument("--warmup", type=int, default=10, help="Number of warmup iterations")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON path")
    args = parser.parse_args()

    run_benchmark(
        weights=args.weights,
        input_size=args.size,
        iterations=args.iterations,
        warmup=args.warmup,
        output_json=args.output,
    )


if __name__ == "__main__":
    main()
