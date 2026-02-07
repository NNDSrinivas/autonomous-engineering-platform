#!/usr/bin/env python3
"""
Real LLM E2E Tests for NAVI Production Readiness

This test suite runs 100+ tests with actual LLM models (not mocks)
to establish performance baselines and validate production readiness.

Usage:
    pytest tests/e2e/test_real_llm.py --real-llm --runs=100
"""

import asyncio
import aiohttp
import json
import os
import time
import yaml
from typing import List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import pytest
import random

# Test configuration
BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8000")
USE_REAL_LLM = os.getenv("USE_REAL_LLM", "false").lower() == "true"
WORKSPACE_ROOT = os.getenv(
    "WORKSPACE_ROOT", "/Users/mounikakapa/dev/autonomous-engineering-platform"
)

# Load test config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "real_llm_config.yaml")

with open(CONFIG_PATH, "r") as f:
    TEST_CONFIG = yaml.safe_load(f)


@dataclass
class TestMetrics:
    """Performance metrics for a single test"""

    test_name: str
    scenario: str
    start_time: float
    end_time: float
    latency_ms: float
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None
    model: str = ""
    provider: str = ""


@dataclass
class TestResults:
    """Aggregated test results"""

    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    total_duration_sec: float = 0.0
    metrics: List[TestMetrics] = field(default_factory=list)

    # Performance statistics
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    latency_avg: float = 0.0
    total_cost: float = 0.0
    error_rate: float = 0.0
    throughput_rps: float = 0.0


# Test scenarios with sample inputs
TEST_SCENARIOS = {
    "code_explanation": [
        "Explain this Python function: def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
        "What does this code do: async def fetch_data(): async with aiohttp.ClientSession() as session: return await session.get('https://api.example.com')",
        "Explain the purpose of this SQL query: SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id",
    ],
    "code_generation": [
        "Write a Python function to check if a number is prime",
        "Create a React component that displays a list of items with pagination",
        "Generate a SQL query to find the top 10 customers by total order value",
    ],
    "bug_analysis": [
        "Why does this code fail: items = [1,2,3]; print(items[3])",
        "Find the bug: def calculate_average(numbers): return sum(numbers) / len(numbers); calculate_average([])",
        "This code is slow, why? for i in range(len(items)): for j in range(len(items)): if items[i] == items[j]: print('duplicate')",
    ],
    "refactoring": [
        "Refactor this for better readability: def f(x,y,z): return x if x>y and x>z else y if y>z else z",
        "Improve this code: data=[]; for i in range(100): data.append(i*2)",
        "Make this more Pythonic: result=[]; for item in items: if item > 0: result.append(item*2)",
    ],
    "documentation": [
        "Generate docstring for: def process_order(order_id, user_id, items): pass",
        "Create API documentation for a REST endpoint that creates a new user",
        "Write a README section explaining how to install and run this project",
    ],
}


class RealLLMTester:
    """Test runner for real LLM scenarios"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.results = TestResults()

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    def _calculate_cost(
        self, tokens_input: int, tokens_output: int, model: str
    ) -> float:
        """Calculate approximate cost based on model pricing"""
        # Pricing varies by model (Feb 2026)
        if "gpt-4o" in model.lower():
            # GPT-4o pricing
            INPUT_COST_PER_1M = 2.50  # $2.50 per 1M input tokens
            OUTPUT_COST_PER_1M = 10.00  # $10 per 1M output tokens
        elif "claude" in model.lower():
            # Claude Sonnet 4 pricing
            INPUT_COST_PER_1M = 3.00  # $3 per 1M input tokens
            OUTPUT_COST_PER_1M = 15.00  # $15 per 1M output tokens
        else:
            # Default pricing
            INPUT_COST_PER_1M = 3.00
            OUTPUT_COST_PER_1M = 15.00

        input_cost = (tokens_input / 1_000_000) * INPUT_COST_PER_1M
        output_cost = (tokens_output / 1_000_000) * OUTPUT_COST_PER_1M

        return input_cost + output_cost

    async def run_single_test(
        self, scenario: str, message: str, test_num: int
    ) -> TestMetrics:
        """Run a single NAVI request with real LLM"""

        test_name = f"{scenario}_{test_num}"
        start_time = time.time()

        payload = {
            "message": message,
            "mode": "agent",
            "workspace_root": WORKSPACE_ROOT,
            "attachments": [],
            "conversationHistory": [],
        }

        try:
            async with self.session.post(
                f"{BASE_URL}/api/navi/chat/stream",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=TEST_CONFIG["timeout_seconds"]),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    end_time = time.time()
                    return TestMetrics(
                        test_name=test_name,
                        scenario=scenario,
                        start_time=start_time,
                        end_time=end_time,
                        latency_ms=(end_time - start_time) * 1000,
                        success=False,
                        error=f"HTTP {response.status}: {error_text[:200]}",
                    )

                # Parse SSE stream
                full_content = ""
                tokens_input = 0
                tokens_output = 0
                model = TEST_CONFIG["model"]
                provider = TEST_CONFIG["llm_provider"]

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)

                        if "content" in data:
                            full_content += data["content"]

                        if "metrics" in data:
                            tokens_input = data["metrics"].get("tokens_input", 0)
                            tokens_output = data["metrics"].get("tokens_output", 0)
                            model = data["metrics"].get("model", model)
                            provider = data["metrics"].get("provider", provider)

                    except json.JSONDecodeError:
                        continue

                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                tokens_total = tokens_input + tokens_output
                cost = self._calculate_cost(tokens_input, tokens_output, model)

                return TestMetrics(
                    test_name=test_name,
                    scenario=scenario,
                    start_time=start_time,
                    end_time=end_time,
                    latency_ms=latency_ms,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    tokens_total=tokens_total,
                    cost_usd=cost,
                    success=True,
                    model=model,
                    provider=provider,
                )

        except Exception as e:
            end_time = time.time()
            return TestMetrics(
                test_name=test_name,
                scenario=scenario,
                start_time=start_time,
                end_time=end_time,
                latency_ms=(end_time - start_time) * 1000,
                success=False,
                error=str(e)[:200],
            )

    async def run_all_tests(self, num_runs: int = 100):
        """Run all test scenarios"""

        print(f"\n🚀 Running {num_runs} tests with real LLM...")
        print(f"Provider: {TEST_CONFIG['llm_provider']}")
        print(f"Model: {TEST_CONFIG['model']}")
        print("=" * 60)

        # Generate test distribution based on weights
        test_queue = []
        for scenario, prompts in TEST_SCENARIOS.items():
            weight = next(
                (
                    s["weight"]
                    for s in TEST_CONFIG["test_scenarios"]
                    if s["name"] == scenario
                ),
                10,
            )
            num_tests = int(num_runs * weight / 100)

            for i in range(num_tests):
                prompt = random.choice(prompts)
                test_queue.append((scenario, prompt, i))

        # Run tests
        start_time = time.time()

        for idx, (scenario, prompt, test_num) in enumerate(test_queue, 1):
            print(f"\n[{idx}/{len(test_queue)}] Running {scenario} test...")

            metric = await self.run_single_test(scenario, prompt, test_num)
            self.results.metrics.append(metric)

            if metric.success:
                print(
                    f"  ✓ Success - {metric.latency_ms:.0f}ms, "
                    f"{metric.tokens_total} tokens, ${metric.cost_usd:.4f}"
                )
                self.results.passed_tests += 1
            else:
                print(f"  ✗ Failed - {metric.error}")
                self.results.failed_tests += 1

            self.results.total_tests += 1

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

        end_time = time.time()
        self.results.total_duration_sec = end_time - start_time

        # Calculate statistics
        self._calculate_statistics()

        return self.results

    def _calculate_statistics(self):
        """Calculate performance statistics"""

        successful_metrics = [m for m in self.results.metrics if m.success]

        if not successful_metrics:
            return

        latencies = sorted([m.latency_ms for m in successful_metrics])

        self.results.latency_avg = sum(latencies) / len(latencies)
        self.results.latency_p50 = latencies[int(len(latencies) * 0.50)]
        self.results.latency_p95 = latencies[int(len(latencies) * 0.95)]
        self.results.latency_p99 = latencies[int(len(latencies) * 0.99)]

        self.results.total_cost = sum(m.cost_usd for m in successful_metrics)
        self.results.error_rate = (
            self.results.failed_tests / self.results.total_tests * 100
            if self.results.total_tests > 0
            else 0
        )
        self.results.throughput_rps = (
            self.results.total_tests / self.results.total_duration_sec
            if self.results.total_duration_sec > 0
            else 0
        )


# Pytest fixtures and tests
@pytest.fixture
async def llm_tester():
    """Create LLM tester instance"""
    async with RealLLMTester() as tester:
        yield tester


@pytest.mark.asyncio
@pytest.mark.skipif(not USE_REAL_LLM, reason="USE_REAL_LLM not set")
async def test_real_llm_performance(llm_tester):
    """
    Run 100+ real LLM tests and validate performance thresholds
    """

    # Get number of runs from command line or default to 100
    num_runs = int(os.getenv("TEST_RUNS", "100"))

    # Run all tests
    results = await llm_tester.run_all_tests(num_runs)

    # Print summary
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {results.total_tests}")
    print(
        f"Passed: {results.passed_tests} ({results.passed_tests/results.total_tests*100:.1f}%)"
    )
    print(f"Failed: {results.failed_tests} ({results.error_rate:.1f}%)")
    print(f"Duration: {results.total_duration_sec:.1f}s")
    print("\nLatency (ms):")
    print(f"  Average: {results.latency_avg:.0f}")
    print(f"  p50: {results.latency_p50:.0f}")
    print(f"  p95: {results.latency_p95:.0f}")
    print(f"  p99: {results.latency_p99:.0f}")
    print(
        f"\nCost: ${results.total_cost:.4f} (avg ${results.total_cost/results.total_tests:.4f} per request)"
    )
    print(f"Throughput: {results.throughput_rps:.2f} requests/sec")
    print("=" * 60)

    # Save results to JSON
    output_file = os.getenv("TEST_OUTPUT", "docs/performance_results/latest.json")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "config": TEST_CONFIG,
                "summary": {
                    "total_tests": results.total_tests,
                    "passed_tests": results.passed_tests,
                    "failed_tests": results.failed_tests,
                    "total_duration_sec": results.total_duration_sec,
                    "latency_avg": results.latency_avg,
                    "latency_p50": results.latency_p50,
                    "latency_p95": results.latency_p95,
                    "latency_p99": results.latency_p99,
                    "total_cost": results.total_cost,
                    "error_rate": results.error_rate,
                    "throughput_rps": results.throughput_rps,
                },
                "metrics": [asdict(m) for m in results.metrics],
            },
            f,
            indent=2,
        )

    print(f"\n✅ Results saved to: {output_file}\n")

    # Assert against performance thresholds
    thresholds = TEST_CONFIG["performance_thresholds"]

    assert (
        results.latency_p50 < thresholds["p50_latency_ms"]
    ), f"p50 latency {results.latency_p50:.0f}ms exceeds threshold {thresholds['p50_latency_ms']}ms"

    assert (
        results.latency_p95 < thresholds["p95_latency_ms"]
    ), f"p95 latency {results.latency_p95:.0f}ms exceeds threshold {thresholds['p95_latency_ms']}ms"

    assert (
        results.latency_p99 < thresholds["p99_latency_ms"]
    ), f"p99 latency {results.latency_p99:.0f}ms exceeds threshold {thresholds['p99_latency_ms']}ms"

    assert (
        results.error_rate < thresholds["error_rate_percent"]
    ), f"Error rate {results.error_rate:.1f}% exceeds threshold {thresholds['error_rate_percent']}%"

    avg_cost = results.total_cost / results.total_tests
    assert (
        avg_cost < thresholds["avg_cost_per_request"]
    ), f"Average cost ${avg_cost:.4f} exceeds threshold ${thresholds['avg_cost_per_request']}"

    print("✅ All performance thresholds met!")


if __name__ == "__main__":
    # Run directly without pytest
    async def main():
        async with RealLLMTester() as tester:
            await tester.run_all_tests(100)

    asyncio.run(main())
