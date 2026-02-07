# Real LLM Testing Infrastructure - Setup Complete ✅

**Date:** February 6, 2026 (Monday - Week 1, Day 1)
**Status:** ✅ COMPLETE
**Deliverable:** Real LLM E2E testing infrastructure ready for execution

---

## What Was Built

A complete testing infrastructure to run 100+ E2E tests with **real LLM models** (not mocks) to establish production performance baselines.

### Components Created

1. **Test Configuration** - [tests/e2e/real_llm_config.yaml](../tests/e2e/real_llm_config.yaml)
   - LLM provider settings (Anthropic Claude Sonnet 4)
   - Performance thresholds (p50/p95/p99 latency, error rate, cost)
   - Test scenario distribution (code explanation, generation, bug analysis, etc.)
   - 100 test runs with 5 concurrent requests

2. **Test Suite** - [tests/e2e/test_real_llm.py](../tests/e2e/test_real_llm.py)
   - 300+ lines of Python test code
   - 5 test scenarios with real-world NAVI tasks
   - Async execution with aiohttp
   - Comprehensive metrics collection (latency, tokens, cost)
   - JSON output for analysis

3. **Test Runner** - [scripts/run_real_llm_tests.sh](../scripts/run_real_llm_tests.sh)
   - Prerequisites checking (API keys, backend health)
   - Automated test execution
   - Performance analysis
   - Report generation
   - Exit code validation

4. **Performance Analyzer** - [scripts/analyze_performance.py](../scripts/analyze_performance.py)
   - Statistical analysis (mean, median, percentiles)
   - Scenario-specific breakdown
   - Threshold validation
   - Console output with color coding

5. **Report Generator** - [scripts/generate_performance_report.py](../scripts/generate_performance_report.py)
   - Markdown report generation
   - Executive summary with pass/fail status
   - Detailed metrics tables
   - Cost projections
   - Recommendations

---

## How to Run

### Prerequisites

1. **API Key**: Set your Anthropic API key
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

2. **Database**: Ensure PostgreSQL is running
   ```bash
   # Check if container is running
   docker ps | grep aep_postgres

   # If not running, start it
   docker run -d --name aep_postgres \
     -e POSTGRES_DB=mentor \
     -e POSTGRES_USER=mentor \
     -e POSTGRES_PASSWORD=mentor \
     -p 5432:5432 \
     pgvector/pgvector:pg15

   export DATABASE_URL="postgresql+psycopg2://mentor:mentor@localhost:5432/mentor"
   ```

3. **Backend**: Start NAVI backend
   ```bash
   ./start_backend_dev.sh

   # Verify it's running
   curl http://localhost:8000/health
   ```

### Run Tests

**Option 1: Using the test runner (recommended)**
```bash
./scripts/run_real_llm_tests.sh
```

This will:
- ✅ Check prerequisites (API keys, backend health)
- ✅ Run 100 tests with real LLM
- ✅ Analyze performance metrics
- ✅ Generate markdown report
- ✅ Validate against thresholds

**Option 2: Using pytest directly**
```bash
export USE_REAL_LLM=true
export ANTHROPIC_API_KEY="sk-ant-..."
export NAVI_BASE_URL="http://localhost:8000"

pytest tests/e2e/test_real_llm.py --real-llm --runs=100 -v
```

**Option 3: Run specific number of tests**
```bash
pytest tests/e2e/test_real_llm.py --real-llm --runs=20 -v  # Quick test
```

### View Results

**Console Output:**
```
🚀 NAVI Real LLM E2E Test Runner
================================================
✓ Prerequisites checked
✓ Backend is running

🧪 Running 100 E2E tests with real LLM...

[1/100] Running code_explanation test...
  ✓ Success - 1234ms, 456 tokens, $0.0123

...

📊 PERFORMANCE SUMMARY
================================================
Total Tests: 100
Passed: 98 (98.0%)
Failed: 2 (2.0%)
Duration: 245.3s

Latency (ms):
  Average: 2145
  p50: 1987
  p95: 3456
  p99: 4123

Cost: $1.2345 (avg $0.0123 per request)
Throughput: 0.41 requests/sec
================================================
```

**JSON Output:**
```bash
cat docs/performance_results/performance_results_20260206_143022.json
```

**Markdown Report:**
```bash
cat docs/PERFORMANCE_BENCHMARKS.md
```

---

## Performance Thresholds

The following thresholds must be met for production deployment:

| Metric | Threshold | Purpose |
|--------|-----------|---------|
| p50 Latency | < 2000ms | Half of users get response within 2s |
| p95 Latency | < 5000ms | 95% of users get response within 5s |
| p99 Latency | < 10000ms | Even slow requests complete within 10s |
| Error Rate | < 5% | At least 95% success rate |
| Avg Cost | < $0.05 | Keep cost per request under 5 cents |

**If thresholds are exceeded:**
- Test suite will fail (exit code 1)
- Performance report will show ❌ status
- Optimization required before production deployment

---

## Test Scenarios

### 1. Code Explanation (30% of tests)
Real-world prompts like:
- "Explain this Python function: ..."
- "What does this SQL query do?"

### 2. Code Generation (25% of tests)
- "Write a Python function to check if a number is prime"
- "Create a React component for pagination"

### 3. Bug Analysis (20% of tests)
- "Why does this code fail: ..."
- "Find the bug in this function"

### 4. Refactoring (15% of tests)
- "Refactor this for better readability"
- "Make this code more Pythonic"

### 5. Documentation (10% of tests)
- "Generate docstring for this function"
- "Write API documentation"

---

## Metrics Collected

For each test request:
- **Latency**: End-to-end response time (ms)
- **Tokens**: Input/output token counts
- **Cost**: Estimated cost based on Anthropic pricing
- **Success**: Boolean (true if HTTP 200 + valid response)
- **Error**: Error message if failed

### Aggregated Metrics
- **Latency distribution**: p50, p95, p99, average
- **Error rate**: % of failed requests
- **Throughput**: Requests per second
- **Total cost**: Sum of all request costs
- **Cost per request**: Average cost
- **Scenario breakdown**: Performance by test type

---

## Files Created

```
tests/e2e/real_llm_config.yaml          # Test configuration
tests/e2e/test_real_llm.py              # Test suite (300+ lines)
scripts/run_real_llm_tests.sh           # Test runner
scripts/analyze_performance.py          # Performance analyzer
scripts/generate_performance_report.py  # Report generator
docs/REAL_LLM_TESTING_SETUP.md         # This file
```

**Output files** (generated after test run):
```
docs/performance_results/performance_results_YYYYMMDD_HHMMSS.json
docs/performance_results/test_execution.log
docs/PERFORMANCE_BENCHMARKS.md
```

---

## Next Steps (Week 1 - Tuesday)

1. **Execute tests**: Run the full 100-test suite
2. **Analyze results**: Review performance benchmarks
3. **Identify bottlenecks**: If thresholds exceeded
4. **Optimize**: Cache, prompt engineering, concurrency
5. **Re-test**: Validate improvements

See [WEEK1_ACTION_PLAN.md](WEEK1_ACTION_PLAN.md) for full schedule.

---

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

### "Backend is not running"
```bash
./start_backend_dev.sh
# Wait 10 seconds for startup
curl http://localhost:8000/health
```

### "Database connection failed"
```bash
docker ps | grep postgres
docker start aep_postgres  # If stopped
export DATABASE_URL="postgresql+psycopg2://mentor:mentor@localhost:5432/mentor"
```

### "ImportError: No module named 'yaml'"
```bash
pip install -r requirements.txt
```

### Tests are too slow
```bash
# Run fewer tests for quick validation
pytest tests/e2e/test_real_llm.py --real-llm --runs=10 -v
```

---

## Cost Estimation

**Per test run (100 tests):**
- Estimated tokens: ~50K input, ~100K output
- Estimated cost: ~$1.50 - $3.00 (depends on prompt complexity)

**Claude Sonnet 4 Pricing (Feb 2026):**
- Input: $3.00 per 1M tokens
- Output: $15.00 per 1M tokens

**Monthly cost (10K requests/day):**
- If avg cost = $0.02/request: $600/month
- If avg cost = $0.05/request: $1,500/month

---

## Integration with CI/CD

**GitHub Actions example:**
```yaml
- name: Run Real LLM Tests
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
    NAVI_BASE_URL: https://staging.navi.example.com
  run: |
    ./scripts/run_real_llm_tests.sh

- name: Upload Performance Report
  uses: actions/upload-artifact@v3
  with:
    name: performance-report
    path: docs/PERFORMANCE_BENCHMARKS.md
```

---

## Success Criteria ✅

- [x] Test configuration created with performance thresholds
- [x] Test suite with 5 real-world scenarios
- [x] Automated test runner with health checks
- [x] Performance analysis with percentile calculations
- [x] Markdown report generation with recommendations
- [x] All dependencies already in requirements.txt
- [x] Documentation complete

**Status: READY FOR EXECUTION** 🚀

Run the tests tomorrow (Tuesday) after confirming API keys are set up.

---

*Created: 2026-02-06*
*Part of: Week 1 Production Launch Plan*
*See: [WEEK1_ACTION_PLAN.md](WEEK1_ACTION_PLAN.md)*
