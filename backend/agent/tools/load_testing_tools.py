"""
Load Testing Tools for Enterprise NAVI.

Provides tools for performance and load testing:
- k6 script generation and execution
- Locust test generation
- Load test result analysis
- Performance baseline establishment

These tools enable testing applications at scale (10M+ users/minute).
"""

import os
import json
import subprocess
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LoadTestConfig:
    """Configuration for a load test."""

    target_url: str
    duration: str = "30s"
    vus: int = 10  # Virtual users
    ramp_up: str = "10s"
    thresholds: Optional[Dict[str, str]] = None


async def loadtest_generate_k6(
    user_id: str,
    target_url: str,
    test_type: str = "smoke",
    endpoints: Optional[List[Dict[str, Any]]] = None,
    duration: str = "30s",
    vus: int = 10,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a k6 load test script.

    k6 is a modern load testing tool built for developer happiness.

    Args:
        user_id: User ID executing the tool
        target_url: Base URL to test (e.g., "https://api.example.com")
        test_type: Type of test - smoke, load, stress, spike, soak
        endpoints: List of endpoints to test [{method, path, body, headers}]
        duration: Test duration (e.g., "30s", "5m", "1h")
        vus: Number of virtual users
        output_path: Path to save the generated script

    Returns:
        Generated k6 script and configuration
    """
    logger.info(
        "[TOOL:loadtest_generate_k6] Generating k6 script",
        target=target_url,
        test_type=test_type,
    )

    # Default endpoints if none provided
    if not endpoints:
        endpoints = [
            {"method": "GET", "path": "/", "name": "homepage"},
            {"method": "GET", "path": "/health", "name": "health_check"},
        ]

    # Test type configurations
    test_configs = {
        "smoke": {
            "stages": [
                {"duration": "1m", "target": 1},
            ],
            "thresholds": {
                "http_req_duration": ["p(95)<500"],
                "http_req_failed": ["rate<0.01"],
            },
            "description": "Smoke test - minimal load to verify system works",
        },
        "load": {
            "stages": [
                {"duration": "2m", "target": vus},
                {"duration": duration, "target": vus},
                {"duration": "1m", "target": 0},
            ],
            "thresholds": {
                "http_req_duration": ["p(95)<500", "p(99)<1000"],
                "http_req_failed": ["rate<0.05"],
            },
            "description": "Load test - typical expected load",
        },
        "stress": {
            "stages": [
                {"duration": "2m", "target": vus},
                {"duration": "5m", "target": vus * 2},
                {"duration": "5m", "target": vus * 4},
                {"duration": "5m", "target": vus * 8},
                {"duration": "2m", "target": 0},
            ],
            "thresholds": {
                "http_req_duration": ["p(95)<2000"],
                "http_req_failed": ["rate<0.1"],
            },
            "description": "Stress test - find breaking point",
        },
        "spike": {
            "stages": [
                {"duration": "1m", "target": vus},
                {"duration": "30s", "target": vus * 10},
                {"duration": "1m", "target": vus * 10},
                {"duration": "30s", "target": vus},
                {"duration": "1m", "target": 0},
            ],
            "thresholds": {
                "http_req_duration": ["p(95)<3000"],
                "http_req_failed": ["rate<0.15"],
            },
            "description": "Spike test - sudden traffic surge",
        },
        "soak": {
            "stages": [
                {"duration": "5m", "target": vus},
                {"duration": "4h", "target": vus},
                {"duration": "5m", "target": 0},
            ],
            "thresholds": {
                "http_req_duration": ["p(95)<500"],
                "http_req_failed": ["rate<0.01"],
            },
            "description": "Soak test - extended period for memory leaks",
        },
    }

    config = test_configs.get(test_type, test_configs["load"])

    # Generate endpoint functions
    endpoint_functions = []
    for i, ep in enumerate(endpoints):
        method = ep.get("method", "GET").upper()
        path = ep.get("path", "/")
        name = ep.get("name", f"endpoint_{i}")
        body = ep.get("body")
        headers = ep.get("headers", {})

        if method == "GET":
            func = f"""
  // {name}
  let {name}_response = http.get(`${{BASE_URL}}{path}`, {{
    tags: {{ name: '{name}' }},
    headers: {json.dumps(headers)},
  }});
  check({name}_response, {{
    '{name} status is 200': (r) => r.status === 200,
    '{name} response time < 500ms': (r) => r.timings.duration < 500,
  }});
  sleep(1);
"""
        else:
            body_str = json.dumps(body) if body else '""'
            func = f"""
  // {name}
  let {name}_response = http.{method.lower()}(`${{BASE_URL}}{path}`, {body_str}, {{
    tags: {{ name: '{name}' }},
    headers: {{ 'Content-Type': 'application/json', ...{json.dumps(headers)} }},
  }});
  check({name}_response, {{
    '{name} status is 200-299': (r) => r.status >= 200 && r.status < 300,
    '{name} response time < 500ms': (r) => r.timings.duration < 500,
  }});
  sleep(1);
"""
        endpoint_functions.append(func)

    # Generate the k6 script
    script = f"""// k6 Load Test Script
// Generated by NAVI Enterprise
// Test Type: {test_type} - {config["description"]}
// Target: {target_url}

import http from 'k6/http';
import {{ check, sleep }} from 'k6';
import {{ Rate, Trend }} from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const responseTime = new Trend('response_time');

// Test configuration
export const options = {{
  stages: {json.dumps(config["stages"], indent=4)},
  thresholds: {json.dumps(config["thresholds"], indent=4)},
  // Output results to JSON for analysis
  // ext: {{ loadimpact: {{ projectID: 12345, name: "{test_type} test" }} }},
}};

const BASE_URL = '{target_url}';

// Setup function - runs once before test
export function setup() {{
  console.log(`Starting {test_type} test against ${{BASE_URL}}`);
  // Verify target is reachable
  let res = http.get(`${{BASE_URL}}/health`);
  if (res.status !== 200) {{
    console.warn('Health check failed, target may be unavailable');
  }}
  return {{ startTime: new Date().toISOString() }};
}}

// Main test function - runs for each virtual user
export default function(data) {{
{"".join(endpoint_functions)}
}}

// Teardown function - runs once after test
export function teardown(data) {{
  console.log(`Test completed. Started at: ${{data.startTime}}`);
}}

// Handle summary at end of test
export function handleSummary(data) {{
  return {{
    'stdout': textSummary(data, {{ indent: ' ', enableColors: true }}),
    'summary.json': JSON.stringify(data, null, 2),
  }};
}}

function textSummary(data, options) {{
  // Basic text summary
  let summary = `
=== {test_type.upper()} TEST RESULTS ===
Duration: ${{data.state.testRunDurationMs}}ms
VUs: ${{data.metrics.vus?.values?.value || 'N/A'}}
Requests: ${{data.metrics.http_reqs?.values?.count || 0}}
Failed: ${{data.metrics.http_req_failed?.values?.passes || 0}}
Avg Response Time: ${{Math.round(data.metrics.http_req_duration?.values?.avg || 0)}}ms
P95 Response Time: ${{Math.round(data.metrics.http_req_duration?.values?.['p(95)'] || 0)}}ms
`;
  return summary;
}}
"""

    # Save if output path provided
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(script)
        logger.info(f"k6 script saved to {output_path}")

    return {
        "success": True,
        "test_type": test_type,
        "target_url": target_url,
        "description": config["description"],
        "stages": config["stages"],
        "thresholds": config["thresholds"],
        "endpoints_count": len(endpoints),
        "script": script,
        "output_path": output_path,
        "run_command": f"k6 run {output_path}" if output_path else "k6 run script.js",
        "message": f"Generated {test_type} k6 script for {target_url} with {len(endpoints)} endpoints",
    }


async def loadtest_generate_locust(
    user_id: str,
    target_url: str,
    endpoints: Optional[List[Dict[str, Any]]] = None,
    users: int = 10,
    spawn_rate: int = 1,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a Locust load test script.

    Locust is a Python-based load testing tool with real-time web UI.

    Args:
        user_id: User ID executing the tool
        target_url: Base URL to test
        endpoints: List of endpoints to test
        users: Number of users to simulate
        spawn_rate: Users spawned per second
        output_path: Path to save the generated script

    Returns:
        Generated Locust script
    """
    logger.info(
        "[TOOL:loadtest_generate_locust] Generating Locust script", target=target_url
    )

    if not endpoints:
        endpoints = [
            {"method": "GET", "path": "/", "name": "homepage", "weight": 3},
            {
                "method": "GET",
                "path": "/api/health",
                "name": "health_check",
                "weight": 1,
            },
        ]

    # Generate task methods
    task_methods = []
    for ep in endpoints:
        method = ep.get("method", "GET").lower()
        path = ep.get("path", "/")
        name = ep.get("name", path.replace("/", "_").strip("_") or "root")
        weight = ep.get("weight", 1)
        body = ep.get("body")

        if method == "get":
            task = f'''
    @task({weight})
    def {name}(self):
        """Test {path}"""
        with self.client.get("{path}", name="{name}", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {{response.status_code}}")
'''
        else:
            body_str = json.dumps(body) if body else "{}"
            task = f'''
    @task({weight})
    def {name}(self):
        """Test {method.upper()} {path}"""
        with self.client.{method}("{path}", json={body_str}, name="{name}", catch_response=True) as response:
            if response.status_code in [200, 201, 204]:
                response.success()
            else:
                response.failure(f"Got status code {{response.status_code}}")
'''
        task_methods.append(task)

    script = f'''"""
Locust Load Test Script
Generated by NAVI Enterprise
Target: {target_url}
"""

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIUser(HttpUser):
    """
    Simulates a user interacting with the API.

    Run with:
        locust -f {output_path or 'locustfile.py'} --host={target_url}

    Or headless:
        locust -f {output_path or 'locustfile.py'} --host={target_url} --headless -u {users} -r {spawn_rate} -t 5m
    """

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts - useful for login flows."""
        logger.info(f"User started: {{self.client.base_url}}")
        # Add authentication here if needed:
        # self.client.post("/login", json={{"username": "test", "password": "test"}})

    def on_stop(self):
        """Called when a user stops."""
        logger.info("User stopped")
{"".join(task_methods)}

# Event hooks for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("Load test starting...")
    if isinstance(environment.runner, MasterRunner):
        logger.info(f"Running distributed test with {{environment.runner.worker_count}} workers")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("Load test finished")
    stats = environment.runner.stats
    logger.info(f"Total requests: {{stats.total.num_requests}}")
    logger.info(f"Failures: {{stats.total.num_failures}}")
    logger.info(f"Average response time: {{stats.total.avg_response_time:.2f}}ms")
    logger.info(f"Requests/sec: {{stats.total.current_rps:.2f}}")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    if exception:
        logger.error(f"Request failed: {{name}} - {{exception}}")
    elif response_time > 1000:
        logger.warning(f"Slow request: {{name}} took {{response_time}}ms")


# Custom shape for ramping (optional)
# from locust import LoadTestShape
# class StagesShape(LoadTestShape):
#     stages = [
#         {{"duration": 60, "users": 10, "spawn_rate": 1}},
#         {{"duration": 120, "users": 50, "spawn_rate": 5}},
#         {{"duration": 180, "users": 100, "spawn_rate": 10}},
#         {{"duration": 240, "users": 50, "spawn_rate": 5}},
#         {{"duration": 300, "users": 0, "spawn_rate": 10}},
#     ]
#
#     def tick(self):
#         run_time = self.get_run_time()
#         for stage in self.stages:
#             if run_time < stage["duration"]:
#                 return (stage["users"], stage["spawn_rate"])
#         return None


if __name__ == "__main__":
    import os
    os.system(f"locust -f {{__file__}} --host={target_url}")
'''

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(script)

    return {
        "success": True,
        "target_url": target_url,
        "endpoints_count": len(endpoints),
        "users": users,
        "spawn_rate": spawn_rate,
        "script": script,
        "output_path": output_path,
        "run_commands": {
            "web_ui": f"locust -f {output_path or 'locustfile.py'} --host={target_url}",
            "headless": f"locust -f {output_path or 'locustfile.py'} --host={target_url} --headless -u {users} -r {spawn_rate} -t 5m",
            "distributed": f"locust -f {output_path or 'locustfile.py'} --master & locust -f {output_path or 'locustfile.py'} --worker",
        },
        "message": f"Generated Locust script for {target_url} with {len(endpoints)} endpoints",
    }


async def loadtest_run(
    user_id: str,
    script_path: str,
    tool: str = "k6",
    duration: str = "30s",
    vus: int = 10,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a load test script.

    Args:
        user_id: User ID executing the tool
        script_path: Path to the load test script
        tool: Load testing tool to use (k6, locust)
        duration: Test duration
        vus: Number of virtual users
        output_path: Path to save results

    Returns:
        Load test execution results
    """
    logger.info("[TOOL:loadtest_run] Running load test", script=script_path, tool=tool)

    if not os.path.exists(script_path):
        return {
            "success": False,
            "error": f"Script not found: {script_path}",
        }

    output_path = output_path or f"loadtest_results_{tool}.json"

    try:
        if tool == "k6":
            cmd = ["k6", "run", "--out", f"json={output_path}", script_path]
            if duration:
                cmd.extend(["--duration", duration])
            if vus:
                cmd.extend(["--vus", str(vus)])
        elif tool == "locust":
            cmd = [
                "locust",
                "-f",
                script_path,
                "--headless",
                "-u",
                str(vus),
                "-r",
                "1",
                "-t",
                duration,
                "--csv",
                output_path.replace(".json", ""),
            ]
        else:
            return {"success": False, "error": f"Unknown tool: {tool}"}

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        return {
            "success": result.returncode == 0,
            "tool": tool,
            "script_path": script_path,
            "duration": duration,
            "vus": vus,
            "stdout": result.stdout[-5000:] if result.stdout else "",  # Last 5000 chars
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "output_path": output_path,
            "return_code": result.returncode,
            "message": f"Load test {'completed' if result.returncode == 0 else 'failed'}",
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Load test timed out after 10 minutes",
            "tool": tool,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": f"{tool} is not installed. Install with: {'brew install k6' if tool == 'k6' else 'pip install locust'}",
            "tool": tool,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "tool": tool,
        }


async def loadtest_analyze_results(
    user_id: str,
    results_path: str,
) -> Dict[str, Any]:
    """
    Analyze load test results and provide insights.

    Args:
        user_id: User ID executing the tool
        results_path: Path to load test results file

    Returns:
        Analysis with insights and recommendations
    """
    logger.info("[TOOL:loadtest_analyze_results] Analyzing results", path=results_path)

    if not os.path.exists(results_path):
        return {
            "success": False,
            "error": f"Results file not found: {results_path}",
        }

    try:
        with open(results_path, "r") as f:
            if results_path.endswith(".json"):
                data = json.load(f)
            else:
                # Try to parse as k6 output lines
                lines = f.readlines()
                data = {"raw_lines": lines[-100:]}  # Last 100 lines

        # Extract metrics (format depends on tool)
        metrics = data.get("metrics", {})

        # Calculate insights
        insights = []
        recommendations = []

        # Check response times
        http_req_duration = metrics.get("http_req_duration", {})
        avg_duration = http_req_duration.get("avg", 0)
        p95_duration = http_req_duration.get("p(95)", 0)

        if avg_duration > 500:
            insights.append(f"High average response time: {avg_duration:.0f}ms")
            recommendations.append(
                "Consider optimizing slow endpoints or adding caching"
            )
        if p95_duration > 1000:
            insights.append(f"P95 response time is high: {p95_duration:.0f}ms")
            recommendations.append("Investigate outliers causing high P95 latency")

        # Check error rate
        http_req_failed = metrics.get("http_req_failed", {})
        error_rate = http_req_failed.get("rate", 0)
        if error_rate > 0.01:
            insights.append(f"Error rate is {error_rate*100:.2f}%")
            recommendations.append(
                "Investigate failing requests - check logs for errors"
            )

        # Check throughput
        http_reqs = metrics.get("http_reqs", {})
        rps = http_reqs.get("rate", 0)
        if rps < 10:
            insights.append(f"Low throughput: {rps:.2f} requests/second")
            recommendations.append("Consider horizontal scaling or connection pooling")

        return {
            "success": True,
            "results_path": results_path,
            "summary": {
                "avg_response_time_ms": avg_duration,
                "p95_response_time_ms": p95_duration,
                "error_rate": error_rate,
                "requests_per_second": rps,
            },
            "insights": insights
            or ["Performance looks good - no major issues detected"],
            "recommendations": recommendations or ["Continue monitoring in production"],
            "raw_metrics": metrics,
            "message": f"Analyzed load test results: {len(insights)} insights found",
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to analyze results: {str(e)}",
        }


async def loadtest_establish_baseline(
    user_id: str,
    target_url: str,
    endpoints: Optional[List[Dict[str, Any]]] = None,
    workspace_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Establish a performance baseline for an application.

    Runs a series of tests to determine normal performance characteristics.

    Args:
        user_id: User ID executing the tool
        target_url: Base URL to test
        endpoints: Endpoints to test
        workspace_path: Where to save baseline data

    Returns:
        Baseline metrics and thresholds
    """
    logger.info(
        "[TOOL:loadtest_establish_baseline] Establishing baseline", target=target_url
    )

    # Generate a smoke test
    smoke_result = await loadtest_generate_k6(
        user_id=user_id,
        target_url=target_url,
        test_type="smoke",
        endpoints=endpoints,
        output_path=(
            os.path.join(workspace_path, "baseline_smoke.js")
            if workspace_path
            else None
        ),
    )

    # Recommended thresholds based on typical SLAs
    recommended_thresholds = {
        "response_time_avg_ms": 200,
        "response_time_p95_ms": 500,
        "response_time_p99_ms": 1000,
        "error_rate_max": 0.01,  # 1%
        "throughput_min_rps": 100,
    }

    return {
        "success": True,
        "target_url": target_url,
        "smoke_test_script": smoke_result.get("output_path"),
        "recommended_thresholds": recommended_thresholds,
        "baseline_test_plan": [
            {"test": "smoke", "purpose": "Verify system works under minimal load"},
            {"test": "load", "purpose": "Verify system handles expected load"},
            {"test": "stress", "purpose": "Find breaking point"},
        ],
        "next_steps": [
            "1. Run the smoke test to verify basic functionality",
            "2. Run a load test with expected user count",
            "3. Run a stress test to find limits",
            "4. Save results as baseline for future comparisons",
        ],
        "message": f"Baseline configuration created for {target_url}",
    }


# Tool definitions for NAVI agent
LOAD_TESTING_TOOLS = {
    "loadtest_generate_k6": {
        "function": loadtest_generate_k6,
        "description": "Generate a k6 load test script for performance testing",
        "parameters": {
            "type": "object",
            "properties": {
                "target_url": {"type": "string", "description": "Base URL to test"},
                "test_type": {
                    "type": "string",
                    "enum": ["smoke", "load", "stress", "spike", "soak"],
                    "description": "Type of load test",
                },
                "endpoints": {
                    "type": "array",
                    "description": "Endpoints to test [{method, path, name, body}]",
                },
                "duration": {
                    "type": "string",
                    "description": "Test duration (e.g., 30s, 5m)",
                },
                "vus": {"type": "integer", "description": "Number of virtual users"},
                "output_path": {"type": "string", "description": "Path to save script"},
            },
            "required": ["target_url"],
        },
    },
    "loadtest_generate_locust": {
        "function": loadtest_generate_locust,
        "description": "Generate a Locust load test script (Python-based with web UI)",
        "parameters": {
            "type": "object",
            "properties": {
                "target_url": {"type": "string", "description": "Base URL to test"},
                "endpoints": {"type": "array", "description": "Endpoints to test"},
                "users": {
                    "type": "integer",
                    "description": "Number of users to simulate",
                },
                "spawn_rate": {
                    "type": "integer",
                    "description": "Users spawned per second",
                },
                "output_path": {"type": "string", "description": "Path to save script"},
            },
            "required": ["target_url"],
        },
    },
    "loadtest_run": {
        "function": loadtest_run,
        "description": "Execute a load test script (k6 or Locust)",
        "parameters": {
            "type": "object",
            "properties": {
                "script_path": {
                    "type": "string",
                    "description": "Path to load test script",
                },
                "tool": {
                    "type": "string",
                    "enum": ["k6", "locust"],
                    "description": "Load testing tool",
                },
                "duration": {"type": "string", "description": "Test duration"},
                "vus": {"type": "integer", "description": "Virtual users"},
                "output_path": {
                    "type": "string",
                    "description": "Path to save results",
                },
            },
            "required": ["script_path"],
        },
    },
    "loadtest_analyze_results": {
        "function": loadtest_analyze_results,
        "description": "Analyze load test results and provide insights",
        "parameters": {
            "type": "object",
            "properties": {
                "results_path": {
                    "type": "string",
                    "description": "Path to results file",
                },
            },
            "required": ["results_path"],
        },
    },
    "loadtest_establish_baseline": {
        "function": loadtest_establish_baseline,
        "description": "Establish performance baseline for an application",
        "parameters": {
            "type": "object",
            "properties": {
                "target_url": {"type": "string", "description": "Base URL to test"},
                "endpoints": {"type": "array", "description": "Endpoints to test"},
                "workspace_path": {
                    "type": "string",
                    "description": "Where to save baseline",
                },
            },
            "required": ["target_url"],
        },
    },
}
