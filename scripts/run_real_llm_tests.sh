#!/bin/bash
# Real LLM E2E Test Runner
# Run 100+ tests with actual LLM models to establish performance baselines
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 NAVI Real LLM E2E Test Runner${NC}"
echo "================================================"

# 1. Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

# Check for API keys based on test config
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}ERROR: No API key set${NC}"
    echo "Please set either:"
    echo "  export ANTHROPIC_API_KEY=your-key-here  (for Claude)"
    echo "  export OPENAI_API_KEY=your-key-here     (for GPT)"
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}WARNING: DATABASE_URL not set, metrics won't be persisted${NC}"
    export DATABASE_URL="postgresql+psycopg2://mentor:mentor@localhost:5432/mentor"
fi

# 2. Environment setup
export USE_REAL_LLM=true
export TRACK_PERFORMANCE_METRICS=true
export NAVI_BASE_URL="${NAVI_BASE_URL:-http://127.0.0.1:8787}"
export TEST_OUTPUT_DIR="docs/performance_results"

mkdir -p "$TEST_OUTPUT_DIR"

echo -e "${GREEN}✓ Prerequisites checked${NC}"
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "  - ANTHROPIC_API_KEY: Set (using Claude)"
fi
if [ -n "$OPENAI_API_KEY" ]; then
    echo "  - OPENAI_API_KEY: Set (using GPT)"
fi
echo "  - DATABASE_URL: $DATABASE_URL"
echo "  - NAVI_BASE_URL: $NAVI_BASE_URL"

# 3. Check if backend is running
echo -e "\n${YELLOW}Checking if NAVI backend is running...${NC}"
if curl -s -f "$NAVI_BASE_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is running${NC}"
else
    echo -e "${RED}ERROR: Backend is not running at $NAVI_BASE_URL${NC}"
    echo "Please start the backend first: ./start_backend_dev.sh"
    exit 1
fi

# 4. Run tests
echo -e "\n${YELLOW}🧪 Running 100 E2E tests with real LLM...${NC}"
echo "This will take approximately 10-15 minutes"
echo "================================================"

OUTPUT_FILE="$TEST_OUTPUT_DIR/performance_results_$(date +%Y%m%d_%H%M%S).json"

# Set environment variables for the test
export TEST_RUNS=100
export TEST_OUTPUT="$OUTPUT_FILE"

pytest tests/e2e/test_real_llm.py::test_real_llm_performance \
  -v \
  -s 2>&1 | tee "$TEST_OUTPUT_DIR/test_execution.log"

TEST_EXIT_CODE=${PIPESTATUS[0]}

# 5. Analyze results
echo -e "\n${YELLOW}📊 Analyzing performance results...${NC}"
python3 scripts/analyze_performance.py "$OUTPUT_FILE"

ANALYSIS_EXIT_CODE=$?

# 6. Generate markdown report
echo -e "\n${YELLOW}📝 Generating performance report...${NC}"
REPORT_FILE="docs/PERFORMANCE_BENCHMARKS.md"
python3 scripts/generate_performance_report.py "$OUTPUT_FILE" "$REPORT_FILE"

echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}✅ Real LLM tests complete${NC}"
echo -e "Results: $OUTPUT_FILE"
echo -e "Report: $REPORT_FILE"
echo -e "Logs: $TEST_OUTPUT_DIR/test_execution.log"

# 7. Summary
if [ $TEST_EXIT_CODE -eq 0 ] && [ $ANALYSIS_EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}✓ All tests passed and performance is within thresholds${NC}"
    exit 0
else
    echo -e "\n${RED}✗ Some tests failed or performance thresholds exceeded${NC}"
    echo -e "Check the report for details: $REPORT_FILE"
    exit 1
fi
