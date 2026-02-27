#!/usr/bin/env python3
"""
Performance Results Analyzer

Analyzes JSON output from real LLM tests and generates insights.
"""

import json
import sys
from typing import Dict, List
from datetime import datetime
import statistics


def load_results(filepath: str) -> Dict:
    """Load test results from JSON file"""
    with open(filepath, "r") as f:
        return json.load(f)


def analyze_by_scenario(metrics: List[Dict]) -> Dict:
    """Analyze metrics grouped by scenario"""

    scenarios = {}

    for metric in metrics:
        scenario = metric["scenario"]
        if scenario not in scenarios:
            scenarios[scenario] = {
                "count": 0,
                "latencies": [],
                "tokens": [],
                "costs": [],
                "errors": 0,
            }

        scenarios[scenario]["count"] += 1

        if metric["success"]:
            scenarios[scenario]["latencies"].append(metric["latency_ms"])
            scenarios[scenario]["tokens"].append(metric["tokens_total"])
            scenarios[scenario]["costs"].append(metric["cost_usd"])
        else:
            scenarios[scenario]["errors"] += 1

    # Calculate statistics per scenario
    results = {}
    for scenario, data in scenarios.items():
        if data["latencies"]:
            results[scenario] = {
                "count": data["count"],
                "latency_avg": statistics.mean(data["latencies"]),
                "latency_median": statistics.median(data["latencies"]),
                "latency_stdev": (
                    statistics.stdev(data["latencies"])
                    if len(data["latencies"]) > 1
                    else 0
                ),
                "tokens_avg": statistics.mean(data["tokens"]),
                "cost_avg": statistics.mean(data["costs"]),
                "cost_total": sum(data["costs"]),
                "error_count": data["errors"],
                "error_rate": data["errors"] / data["count"] * 100,
            }
        else:
            results[scenario] = {
                "count": data["count"],
                "error_count": data["errors"],
                "error_rate": 100.0,
            }

    return results


def print_analysis(results: Dict):
    """Print analysis results to console"""

    print("\n" + "=" * 80)
    print("📊 PERFORMANCE ANALYSIS")
    print("=" * 80)

    # Overall summary
    summary = results["summary"]
    print(f"\n🎯 Overall Performance:")
    print(f"  Total Tests: {summary['total_tests']}")
    print(
        f"  Success Rate: {(summary['passed_tests'] / summary['total_tests'] * 100):.1f}%"
    )
    print(f"  Error Rate: {summary['error_rate']:.2f}%")
    print(f"  Duration: {summary['total_duration_sec']:.1f}s")
    print(f"  Throughput: {summary['throughput_rps']:.2f} req/s")

    # Latency breakdown
    print(f"\n⚡ Latency (milliseconds):")
    print(f"  Average: {summary['latency_avg']:.0f}ms")
    print(f"  p50:     {summary['latency_p50']:.0f}ms")
    print(f"  p95:     {summary['latency_p95']:.0f}ms")
    print(f"  p99:     {summary['latency_p99']:.0f}ms")

    # Cost breakdown
    print(f"\n💰 Cost Analysis:")
    print(f"  Total:   ${summary['total_cost']:.4f}")
    print(
        f"  Average: ${(summary['total_cost'] / summary['total_tests']):.4f} per request"
    )
    print(
        f"  Estimated monthly (10K req/day): ${(summary['total_cost'] / summary['total_tests'] * 10000 * 30):.2f}"
    )

    # Scenario-specific analysis
    scenario_analysis = analyze_by_scenario(results["metrics"])

    print(f"\n📋 Performance by Scenario:")
    print("-" * 80)
    print(
        f"{'Scenario':<20} {'Count':>6} {'Avg Latency':>12} {'Avg Cost':>10} {'Error Rate':>11}"
    )
    print("-" * 80)

    for scenario, data in sorted(scenario_analysis.items()):
        latency = (
            f"{data.get('latency_avg', 0):.0f}ms" if "latency_avg" in data else "N/A"
        )
        cost = f"${data.get('cost_avg', 0):.4f}" if "cost_avg" in data else "N/A"
        error_rate = f"{data['error_rate']:.1f}%"

        print(
            f"{scenario:<20} {data['count']:>6} {latency:>12} {cost:>10} {error_rate:>11}"
        )

    print("-" * 80)

    # Threshold validation
    config = results["config"]
    thresholds = config["performance_thresholds"]

    print(f"\n✅ Threshold Validation:")
    print("-" * 80)

    def check_threshold(metric_name, value, threshold, lower_is_better=True):
        if lower_is_better:
            passed = value < threshold
            symbol = "✓" if passed else "✗"
            comparison = "<" if passed else "≥"
        else:
            passed = value > threshold
            symbol = "✓" if passed else "✗"
            comparison = ">" if passed else "≤"

        print(
            f"  {symbol} {metric_name}: {value:.2f} {comparison} {threshold} {'✓' if passed else '✗ FAILED'}"
        )
        return passed

    all_passed = True
    all_passed &= check_threshold(
        "p50 Latency (ms)", summary["latency_p50"], thresholds["p50_latency_ms"]
    )
    all_passed &= check_threshold(
        "p95 Latency (ms)", summary["latency_p95"], thresholds["p95_latency_ms"]
    )
    all_passed &= check_threshold(
        "p99 Latency (ms)", summary["latency_p99"], thresholds["p99_latency_ms"]
    )
    all_passed &= check_threshold(
        "Error Rate (%)", summary["error_rate"], thresholds["error_rate_percent"]
    )

    avg_cost = summary["total_cost"] / summary["total_tests"]
    all_passed &= check_threshold(
        "Avg Cost ($)", avg_cost, thresholds["avg_cost_per_request"]
    )

    print("-" * 80)

    if all_passed:
        print(f"\n✅ All performance thresholds met! Ready for production.")
    else:
        print(
            f"\n❌ Some thresholds exceeded. Review performance before production deployment."
        )

    print("=" * 80 + "\n")

    return 0 if all_passed else 1


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_performance.py <results.json>")
        sys.exit(1)

    filepath = sys.argv[1]

    try:
        results = load_results(filepath)
        exit_code = print_analysis(results)
        sys.exit(exit_code)
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
