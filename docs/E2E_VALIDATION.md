# NAVI Real LLM E2E Validation Guide

**Last Updated:** February 7, 2026

## Overview

This document describes NAVI's comprehensive End-to-End (E2E) validation testing with **real LLM models** (not mocks). The validation suite measures real-world performance, reliability, and error handling across 100+ test scenarios.

---

## Why Real LLM Validation Matters

### The Problem with Mocked Tests

- **Mocked tests** use fake LLM responses → don't reflect real performance
- **Unknown latency:** Real API calls to Claude/GPT have variable latency (500ms - 10s+)
- **Unknown error rates:** Real APIs have rate limits, quotas, and transient failures
- **Unknown behavior:** Real model responses vary based on prompt, temperature, and model version

### Real LLM Validation Benefits

- ✅ **Accurate performance metrics:** Measure p50/p95/p99 latency with real API calls
- ✅ **Real error handling:** Test rate limits, quota exceeded, network failures
- ✅ **Production confidence:** Know how NAVI performs under real conditions
- ✅ **SLO validation:** Verify P95 latency < 5 seconds target
- ✅ **Model comparison:** Compare Claude vs GPT-4 performance

---

## Test Suite Overview

### Test Categories

| Category | Count | Iterations | Timeout | Description |
|----------|-------|------------|---------|-------------|
| **Simple** | 40 | 1-8 | 120s | Single-step operations (file reads, git status, searches) |
| **Medium** | 30 | 8-15 | 180s | Multi-step operations (code analysis, dependency tracking) |
| **Complex** | 20 | 15-25 | 240s | Advanced tasks (refactoring, security audits, architecture review) |
| **Enterprise** | 10 | Unlimited | 300s | End-to-end workflows (full codebase analysis, migration planning) |

### Total Test Coverage

- **100+ test scenarios** covering real-world NAVI usage
- **10+ categories:** File operations, code analysis, git operations, search, refactoring, security, performance, architecture, testing, documentation
- **15+ tool types:** read_file, glob, grep, bash, edit_file, write_file, delete_file, move_file, etc.

---

## Running Validation Tests

### Prerequisites

1. **Backend running:**
   ```bash
   ./start_backend_dev.sh
   # Backend should be running on http://127.0.0.1:8787
   ```

2. **API keys configured:**
   ```bash
   # Ensure ANTHROPIC_API_KEY or OPENAI_API_KEY is set
   export ANTHROPIC_API_KEY="sk-ant-..."
   # OR
   export OPENAI_API_KEY="sk-..."
   ```

3. **Python dependencies:**
   ```bash
   pip install httpx
   ```

### Quick Validation (5 tests, ~2 minutes)

```bash
make e2e-validation-quick
```

**What it tests:**
- File read (README.md)
- List Python files
- Git status check
- Count lines of code
- Check dependencies

**Output:**
- `tmp/e2e_validation_report.json` - JSON results
- `tmp/e2e_validation_report.md` - Markdown report
- `tmp/e2e_validation_report.html` - Interactive HTML report

### Medium Validation (30 tests, ~10 minutes)

```bash
make e2e-validation-medium
```

**What it tests:**
- All simple tests
- Code searches and imports
- Module analysis
- Directory structure review
- Test coverage checks

### Full Validation (100 tests, ~40 minutes)

```bash
make e2e-validation-full
```

**What it tests:**
- All test categories (simple, medium, complex, enterprise)
- Comprehensive coverage of NAVI capabilities
- Real-world production scenarios

**Note:** Runs 3 tests concurrently to speed up execution.

### Benchmark Validation (100 tests for benchmarking)

```bash
make e2e-validation-benchmark
```

**What it does:**
- Runs first 100 tests from full suite
- Generates comprehensive performance report
- Used for production readiness gate

---

## Command Line Options

### Basic Usage

```bash
python scripts/e2e_real_llm_validation.py [options]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--suite` | `quick` | Test suite: `quick`, `medium`, `complex`, or `full` |
| `--model` | `claude-sonnet-4` | Model identifier for reporting |
| `--base-url` | `http://127.0.0.1:8787` | NAVI API base URL |
| `--output` | `tmp/e2e_validation_report.json` | JSON output file path |
| `--report-md` | `false` | Generate Markdown report |
| `--report-html` | `false` | Generate HTML report |
| `--max-concurrent` | `1` | Maximum concurrent tests (1-10) |
| `--count` | `all` | Override number of tests (takes first N) |

### Examples

**Run 50 tests and generate all reports:**
```bash
python scripts/e2e_real_llm_validation.py \
  --suite full \
  --count 50 \
  --report-md \
  --report-html \
  --max-concurrent 3
```

**Test with GPT-4 instead of Claude:**
```bash
python scripts/e2e_real_llm_validation.py \
  --suite quick \
  --model gpt-4o \
  --report-md
```

**Production staging test:**
```bash
python scripts/e2e_real_llm_validation.py \
  --suite full \
  --base-url https://staging.example.com \
  --report-md \
  --report-html \
  --max-concurrent 5
```

---

## Understanding the Reports

### JSON Report Structure

```json
{
  "metadata": {
    "start_time": "2026-02-07T10:00:00",
    "end_time": "2026-02-07T10:45:23",
    "total_duration_seconds": 2723.45,
    "model": "claude-sonnet-4"
  },
  "summary": {
    "total_tests": 100,
    "passed": 95,
    "failed": 5,
    "success_rate": 95.0
  },
  "latency": {
    "p50_ms": 1234.56,
    "p95_ms": 4567.89,
    "p99_ms": 8901.23,
    "avg_ms": 2345.67
  },
  "by_category": {
    "simple": {
      "total": 40,
      "passed": 40,
      "failed": 0,
      "success_rate": 100.0,
      "avg_latency_ms": 856.32,
      "p95_latency_ms": 1234.56
    },
    ...
  },
  "errors": [
    {
      "test_id": "complex_003",
      "test_name": "Security review",
      "error": "timeout after 240s"
    }
  ],
  "detailed_results": [
    {
      "test_id": "simple_001",
      "test_name": "File read - README",
      "category": "simple",
      "success": true,
      "duration_ms": 1234.56,
      "iterations_used": 3,
      "tool_calls_made": ["read_file"],
      "error": null,
      "timestamp": "2026-02-07T10:01:23"
    },
    ...
  ]
}
```

### Markdown Report Sections

1. **Executive Summary** - Total tests, pass/fail, success rate
2. **Latency Metrics** - P50, P95, P99, Average
3. **SLO Compliance** - Target vs Actual (P95 < 5000ms)
4. **Results by Category** - Performance breakdown by test category
5. **Failed Tests** - Detailed error information
6. **Recommendations** - Actionable improvements
7. **Detailed Results** - Full test results table

### HTML Report Features

- **Interactive dashboard** with metrics cards
- **Color-coded results** (green=success, red=error, yellow=warning)
- **Sortable tables** for detailed results
- **Visual charts** for latency distribution (future enhancement)
- **Responsive design** for mobile/desktop viewing

---

## Interpreting Results

### Success Criteria

| Metric | Target | Status |
|--------|--------|--------|
| **Success Rate** | ≥ 95% | ✅ Excellent / ⚠️ Needs improvement / ❌ Critical |
| **P95 Latency** | < 5000ms | ✅ SLO met / ❌ SLO missed |
| **P99 Latency** | < 10000ms | ✅ Good / ⚠️ Acceptable / ❌ Poor |
| **Error Rate** | < 1% | ✅ Acceptable / ❌ Too high |

### Performance Ratings

**Latency (P95):**
- **Excellent:** < 2000ms
- **Good:** 2000-5000ms (meets SLO)
- **Acceptable:** 5000-10000ms (needs optimization)
- **Poor:** > 10000ms (critical issue)

**Success Rate:**
- **Excellent:** ≥ 95%
- **Good:** 90-95%
- **Acceptable:** 80-90%
- **Poor:** < 80%

### Common Failure Reasons

1. **Timeouts:**
   - **Cause:** LLM response took too long
   - **Fix:** Increase timeout or optimize prompt

2. **Rate Limits:**
   - **Cause:** API quota exceeded
   - **Fix:** Reduce concurrency or increase quota

3. **Network Errors:**
   - **Cause:** Connection to backend/LLM failed
   - **Fix:** Check network, retry failed tests

4. **Tool Execution Errors:**
   - **Cause:** Tool failed (e.g., file not found)
   - **Fix:** Verify test assumptions and workspace state

---

## Production Readiness Gate

### Requirements

Before NAVI can be marked production-ready, the following validation criteria must be met:

- [x] **Test script created** (e2e_real_llm_validation.py)
- [ ] **100+ tests executed** with real LLM models
- [ ] **Success rate ≥ 95%** (95+ out of 100 tests pass)
- [ ] **P95 latency < 5000ms** (SLO compliance)
- [ ] **P99 latency < 10000ms** (tail latency acceptable)
- [ ] **Error recovery validated** (rate limits, timeouts, network failures)
- [ ] **Performance report generated** and reviewed
- [ ] **Bottlenecks identified** and documented
- [ ] **Optimization plan created** (if SLO not met)

### Validation Checklist

#### Week 1: Initial Validation

- [ ] Run quick suite (5 tests) to verify setup
- [ ] Run medium suite (30 tests) to check stability
- [ ] Run full suite (100 tests) overnight
- [ ] Generate all reports (JSON, MD, HTML)
- [ ] Review results and identify failures

#### Week 2: Optimization & Retry

- [ ] Fix any test failures (tool errors, timeouts)
- [ ] Optimize slow queries if P95 > 5000ms
- [ ] Re-run failed tests individually
- [ ] Run full suite again to confirm fixes
- [ ] Document performance characteristics

#### Week 3: Production Readiness

- [ ] Achieve 95%+ success rate
- [ ] Achieve P95 < 5000ms
- [ ] Document error handling procedures
- [ ] Create performance baseline
- [ ] Mark production readiness task complete

---

## CI/CD Integration

### GitHub Actions Workflow

Add to `.github/workflows/e2e-validation.yml`:

```yaml
name: E2E Validation (Real LLM)

on:
  schedule:
    - cron: '0 2 * * *'  # Run daily at 2 AM
  workflow_dispatch:
    inputs:
      suite:
        description: 'Test suite to run'
        required: true
        default: 'quick'
        type: choice
        options:
          - quick
          - medium
          - full

jobs:
  e2e-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install httpx
          pip install -r requirements.txt

      - name: Start backend
        run: |
          uvicorn backend.api.main:app --host 0.0.0.0 --port 8787 &
          sleep 10

      - name: Run E2E validation
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python scripts/e2e_real_llm_validation.py \
            --suite ${{ github.event.inputs.suite || 'quick' }} \
            --report-md \
            --report-html

      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: e2e-validation-reports
          path: |
            tmp/e2e_validation_report.json
            tmp/e2e_validation_report.md
            tmp/e2e_validation_report.html

      - name: Check SLO compliance
        run: |
          # Parse JSON report and fail if P95 > 5000ms or success rate < 95%
          python scripts/check_e2e_slo.py tmp/e2e_validation_report.json
```

---

## Monitoring & Alerting

### Recommended Alerts

**Critical Alerts:**
- Success rate drops below 90%
- P95 latency exceeds 10 seconds
- More than 5% error rate

**Warning Alerts:**
- Success rate drops below 95%
- P95 latency exceeds 5 seconds (SLO breach)
- Any test category has 100% failure rate

### Grafana Dashboard

Create dashboard panels for:
- **Success rate trend** (daily)
- **Latency percentiles** (P50, P95, P99)
- **Tests by category** (pass/fail breakdown)
- **Error types** (timeout, rate limit, network, tool)
- **Model comparison** (Claude vs GPT-4)

---

## Troubleshooting

### Problem: All tests fail with "Connection refused"

**Cause:** Backend not running

**Fix:**
```bash
# Start backend
./start_backend_dev.sh

# Verify it's running
curl http://127.0.0.1:8787/health
```

### Problem: Tests timeout frequently

**Cause:** LLM responses are slow

**Fix:**
1. Check API key has sufficient quota
2. Reduce concurrency: `--max-concurrent 1`
3. Increase timeout in test config
4. Use faster model (e.g., claude-haiku instead of opus)

### Problem: Rate limit errors

**Cause:** Too many concurrent requests

**Fix:**
1. Reduce concurrency: `--max-concurrent 1`
2. Increase delays between tests
3. Upgrade API tier for higher limits

### Problem: Low success rate (<90%)

**Cause:** Tests are flaky or environment issues

**Fix:**
1. Review failed test details in report
2. Run individual failed tests to debug
3. Check workspace state (git clean, files exist)
4. Verify backend logs for errors

### Problem: High latency (P95 > 5000ms)

**Cause:** Slow LLM responses or inefficient prompts

**Fix:**
1. Profile slow tests individually
2. Optimize prompts to reduce token count
3. Use caching for repeated queries
4. Consider faster model tier

---

## Future Enhancements

### Planned Features

- [ ] **Visual latency charts** in HTML report
- [ ] **Model comparison** (Claude vs GPT-4 side-by-side)
- [ ] **Historical trending** (track performance over time)
- [ ] **Detailed tool analytics** (which tools are slowest)
- [ ] **Automatic retry** for transient failures
- [ ] **Parallel test execution** optimization
- [ ] **Custom test suites** via YAML config
- [ ] **Integration with Grafana** for live dashboards

---

## References

- **Test Script:** [scripts/e2e_real_llm_validation.py](../scripts/e2e_real_llm_validation.py)
- **Makefile Targets:** [Makefile](../Makefile)
- **Production Readiness:** [NAVI_PROD_READINESS.md](NAVI_PROD_READINESS.md)
- **CI/CD Workflows:** [.github/workflows/](.github/workflows/)

---

**Last Updated:** February 7, 2026
**Document Version:** 1.0
**Script Version:** 1.0
