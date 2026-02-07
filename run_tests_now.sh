#!/bin/bash
# Quick test runner - Everything is already set up!

echo "🧪 Running Real LLM Tests with OpenAI GPT-4o"
echo "=============================================="

# Environment (must be provided by caller; do NOT hardcode secrets here)
: "${OPENAI_API_KEY:?Please set OPENAI_API_KEY in your environment before running this script}"
: "${DATABASE_URL:=postgresql+psycopg2://mentor:mentor@localhost:5432/mentor}"
export USE_REAL_LLM=true
export NAVI_BASE_URL="http://127.0.0.1:8787"

echo "✅ Database: Running (PostgreSQL on port 5432)"
echo "✅ Backend: Running (NAVI on port 8787)"
echo "✅ API Key: OpenAI GPT-4o configured"
echo ""
echo "Starting test run..."
echo ""

# Run the tests
./scripts/run_real_llm_tests.sh
