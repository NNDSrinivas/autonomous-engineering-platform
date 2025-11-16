#!/bin/bash
# Test NAVI backend health and OpenAI connectivity

echo "🔍 Testing NAVI Backend..."
echo ""

# Check if backend is running
echo "1. Testing health endpoint..."
HEALTH=$(curl -s http://127.0.0.1:8787/api/navi/health)
echo "Response: $HEALTH"
echo ""

# Check if OpenAI is enabled
OPENAI_ENABLED=$(echo $HEALTH | grep -o '"openai_enabled":[^,}]*' | cut -d':' -f2)
echo "2. OpenAI Status:"
if [ "$OPENAI_ENABLED" = "true" ]; then
    echo "   ✅ OpenAI ENABLED - Real LLM responses active"
elif [ "$OPENAI_ENABLED" = "false" ]; then
    echo "   ⚠️  OpenAI DISABLED - Using mock responses"
    echo "   → Set OPENAI_API_KEY to enable real responses"
else
    echo "   ❌ Backend not responding"
    echo "   → Start backend with: uvicorn api.main:app --reload --port 8787"
    exit 1
fi
echo ""

# Test a simple chat request
echo "3. Testing chat endpoint..."
RESPONSE=$(curl -s -X POST http://127.0.0.1:8787/api/navi/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello NAVI",
    "model": "gpt-4",
    "mode": "chat",
    "attachments": []
  }')

if [ $? -eq 0 ]; then
    echo "   ✅ Chat endpoint responding"
    echo "   Response preview: $(echo $RESPONSE | cut -c1-100)..."
else
    echo "   ❌ Chat endpoint failed"
    exit 1
fi
echo ""

echo "✅ All tests passed!"
echo ""
echo "Next steps:"
echo "1. Open VS Code Extension Development Host (F5)"
echo "2. Open NAVI panel"
echo "3. Type 'Hello' and press Enter"
echo "4. You should see a response!"
