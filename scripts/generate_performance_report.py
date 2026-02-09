#!/usr/bin/env python3
"""
Performance Report Generator

Generates a markdown report from real LLM test results.
"""

import json
import sys
from typing import Dict
from datetime import datetime


def load_results(filepath: str) -> Dict:
    """Load test results from JSON file"""
    with open(filepath, "r") as f:
        return json.load(f)


def generate_markdown_report(results: Dict) -> str:
    """Generate markdown report"""

    timestamp = results.get("timestamp", datetime.now().isoformat())
    config = results["config"]
    summary = results["summary"]

    report = f"""# NAVI Performance Benchmarks

**Generated:** {timestamp}
**Model:** {config['model']}
**Provider:** {config['llm_provider']}
**Test Runs:** {summary['total_tests']}

---

## Executive Summary

✅ **Production Readiness:** {'PASS' if summary['error_rate'] < 5 else 'FAIL'}

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Success Rate | {(summary['passed_tests']/summary['total_tests']*100):.1f}% | >95% | {'✅' if summary['error_rate'] < 5 else '❌'} |
| p95 Latency | {summary['latency_p95']:.0f}ms | <{config['performance_thresholds']['p95_latency_ms']}ms | {'✅' if summary['latency_p95'] < config['performance_thresholds']['p95_latency_ms'] else '❌'} |
| p99 Latency | {summary['latency_p99']:.0f}ms | <{config['performance_thresholds']['p99_latency_ms']}ms | {'✅' if summary['latency_p99'] < config['performance_thresholds']['p99_latency_ms'] else '❌'} |
| Avg Cost | ${(summary['total_cost']/summary['total_tests']):.4f} | <${config['performance_thresholds']['avg_cost_per_request']} | {'✅' if (summary['total_cost']/summary['total_tests']) < config['performance_thresholds']['avg_cost_per_request'] else '❌'} |

---

## Performance Metrics

### Latency Distribution

| Percentile | Latency (ms) |
|------------|--------------|
| Average | {summary['latency_avg']:.0f} |
| p50 (median) | {summary['latency_p50']:.0f} |
| p95 | {summary['latency_p95']:.0f} |
| p99 | {summary['latency_p99']:.0f} |

**Interpretation:**
- **p50 ({summary['latency_p50']:.0f}ms):** Half of all requests complete in under {summary['latency_p50']/1000:.1f} seconds
- **p95 ({summary['latency_p95']:.0f}ms):** 95% of requests complete in under {summary['latency_p95']/1000:.1f} seconds
- **p99 ({summary['latency_p99']:.0f}ms):** 99% of requests complete in under {summary['latency_p99']/1000:.1f} seconds

### Throughput

- **Requests per second:** {summary['throughput_rps']:.2f}
- **Total duration:** {summary['total_duration_sec']:.1f} seconds
- **Average request time:** {(summary['total_duration_sec']/summary['total_tests']):.2f} seconds

### Cost Analysis

| Metric | Value |
|--------|-------|
| Total cost (all tests) | ${summary['total_cost']:.4f} |
| Average cost per request | ${(summary['total_cost']/summary['total_tests']):.4f} |
| Estimated daily cost (10K requests) | ${(summary['total_cost']/summary['total_tests']*10000):.2f} |
| Estimated monthly cost (300K requests) | ${(summary['total_cost']/summary['total_tests']*300000):.2f} |

---

## Test Scenarios

The following scenarios were tested based on real-world NAVI usage patterns:

"""

    # Scenario breakdown
    from collections import defaultdict
    scenarios = defaultdict(lambda: {"count": 0, "latencies": [], "costs": []})

    for metric in results["metrics"]:
        if metric["success"]:
            scenario = metric["scenario"]
            scenarios[scenario]["count"] += 1
            scenarios[scenario]["latencies"].append(metric["latency_ms"])
            scenarios[scenario]["costs"].append(metric["cost_usd"])

    report += "| Scenario | Tests | Avg Latency | Avg Cost |\n"
    report += "|----------|-------|-------------|----------|\n"

    for scenario_name in sorted(scenarios.keys()):
        data = scenarios[scenario_name]
        if data["latencies"]:
            avg_latency = sum(data["latencies"]) / len(data["latencies"])
            avg_cost = sum(data["costs"]) / len(data["costs"])
            report += f"| {scenario_name.replace('_', ' ').title()} | {data['count']} | {avg_latency:.0f}ms | ${avg_cost:.4f} |\n"

    report += f"""
---

## Error Analysis

- **Total errors:** {summary['failed_tests']}
- **Error rate:** {summary['error_rate']:.2f}%
- **Successful requests:** {summary['passed_tests']} ({(summary['passed_tests']/summary['total_tests']*100):.1f}%)

"""

    # List errors if any
    errors = [m for m in results["metrics"] if not m["success"]]
    if errors:
        report += "### Error Details\n\n"
        report += "| Test | Scenario | Error |\n"
        report += "|------|----------|-------|\n"
        for error in errors[:10]:  # Show first 10 errors
            report += f"| {error['test_name']} | {error['scenario']} | {error.get('error', 'Unknown')[:50]}... |\n"

        if len(errors) > 10:
            report += f"\n*{len(errors) - 10} more errors not shown*\n"

    report += f"""
---

## Recommendations

"""

    # Generate recommendations based on results
    recommendations = []

    if summary['latency_p95'] > 3000:
        recommendations.append("⚠️ **High p95 latency detected.** Consider implementing response caching for common queries.")

    if summary['error_rate'] > 2:
        recommendations.append("⚠️ **Error rate above 2%.** Investigate failed requests and add retry logic.")

    avg_cost = summary['total_cost'] / summary['total_tests']
    if avg_cost > 0.03:
        recommendations.append(f"💰 **High average cost (${avg_cost:.4f} per request).** Consider using prompt optimization or caching.")

    if summary['throughput_rps'] < 0.5:
        recommendations.append("🐌 **Low throughput detected.** Consider implementing concurrent request processing.")

    if not recommendations:
        recommendations.append("✅ **All metrics look good!** System is ready for production deployment.")

    for rec in recommendations:
        report += f"- {rec}\n"

    report += f"""
---

## Next Steps

1. **Review this report** with the team
2. **Address any performance issues** identified above
3. **Run load tests** with concurrent users (see Week 1 action plan)
4. **Deploy to staging** for real-world validation
5. **Set up monitoring** to track these metrics in production

---

## Appendix: Test Configuration

```yaml
Provider: {config['llm_provider']}
Model: {config['model']}
Test Runs: {summary['total_tests']}
Timeout: {config['timeout_seconds']}s
```

### Performance Thresholds

```yaml
p50_latency_ms: {config['performance_thresholds']['p50_latency_ms']}
p95_latency_ms: {config['performance_thresholds']['p95_latency_ms']}
p99_latency_ms: {config['performance_thresholds']['p99_latency_ms']}
error_rate_percent: {config['performance_thresholds']['error_rate_percent']}
avg_cost_per_request: ${config['performance_thresholds']['avg_cost_per_request']}
```

---

*Generated by NAVI Performance Testing Suite*
*Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    return report


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_performance_report.py <results.json> <output.md>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    try:
        results = load_results(input_file)
        report = generate_markdown_report(results)

        with open(output_file, "w") as f:
            f.write(report)

        print(f"✅ Performance report generated: {output_file}")

    except FileNotFoundError:
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
