# VigilAI Empirical Benchmark Specifications & Execution Guide

**Vishwakarma Awards 2026–27 | Application ID: VK26-AU-HCI-0036**  
**Theme 9: HCI 2.0 (Agentic Hardware & Embodied Intelligent Systems)**

> [!IMPORTANT]
> **Scientific Integrity & No Fabricated Results Policy:**  
> In compliance with strict engineering guidelines, this repository **does not publish synthetic or fabricated performance numbers**. All performance metrics must be measured empirically on target edge devices and host laptops using the provided benchmarking utilities. The result tables below are intentionally designated **[To be filled after running on hardware]**.

---

## 1. Benchmarking Scripts Overview

VigilAI provides two automated benchmarking utilities to measure live compute characteristics:

| Script | Measured Scope | Key Metrics |
|---|---|---|
| [`scripts/benchmark_detector.py`](../scripts/benchmark_detector.py) | Standalone YOLOv8n detector inference at 320px | Inference latency (mean, p50, p95), Throughput (FPS) |
| [`scripts/benchmark_latency.py`](../scripts/benchmark_latency.py) | Full end-to-end Perceive-Reason-Act pipeline | Quality check, Detection, Tracking, Reasoning, Planning, Total Latency |

---

## 2. Benchmark 1: YOLOv8n Detector Throughput (320x320 px)

### Execution Command
Run 100 timed iterations with 10 warmup cycles:

```bash
python scripts/benchmark_detector.py --weights yolov8n.pt --size 320 --iterations 100 --warmup 10 --output results_detector.json
```

### Empirical Hardware Results Table

*Target Specification: Throughput $\ge 15.0\text{ FPS}$ on typical modern CPU.*

| Hardware Platform | Inference Engine | Mean Latency (ms) | Median p50 (ms) | 95th Percentile p95 (ms) | Throughput (FPS) | Status |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **Standard Laptop (Intel Core / AMD Ryzen)** | PyTorch (CPU) | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | Pending run |
| **Raspberry Pi 5 (4GB)** | NCNN Export | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | Pending run |
| **Edge SBC (Orange Pi / Jetson Nano)** | ONNX Runtime | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | Pending run |

---

## 3. Benchmark 2: End-to-End Pipeline Latency

### Execution Command
Run 50 staged end-to-end pipeline evaluations against the 2.0-second real-time limit:

```bash
python scripts/benchmark_latency.py --weights yolov8n.pt --size 320 --events 50 --target 2.0 --output results_latency.json
```

### Empirical Hardware Results Table

*Target Specification: Full Perceive &rarr; Reason &rarr; Act cycle p95 latency $\le 2.0\text{ seconds}$ (2,000 ms).*

| Pipeline Stage | Laptop Host p50 (ms) | Laptop Host p95 (ms) | Raspberry Pi 5 p50 (ms) | Raspberry Pi 5 p95 (ms) |
|---|:---:|:---:|:---:|:---:|
| **1. Quality Assessment (Laplacian/Mean)** | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* |
| **2. YOLOv8n Detector (320px)** | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* |
| **3. Temporal Tracker & Cooldowns** | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* |
| **4. LangGraph Reasoning & Action Plan** | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* |
| **TOTAL END-TO-END PIPELINE LATENCY** | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* |
| **EVALUATION AGAINST 2.0s TARGET** | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* | *[To be filled after running on hardware]* |

---

## 4. Reproducing Benchmarks in Headless or CI Environments

The benchmark scripts operate completely offline and synthesize volatile image arrays directly in RAM without accessing an external camera or physical serial device:

```bash
# Verify entire benchmark suite without hardware connected
python scripts/benchmark_detector.py --size 320 --iterations 10
python scripts/benchmark_latency.py --events 10 --target 2.0
```
