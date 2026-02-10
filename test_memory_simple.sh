#!/bin/bash
# Simple test script for NAVI memory using curl

set -e

# Generate proper UUID for conversation ID (backend expects UUID format)
CONV_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
echo "🧪 Testing NAVI Memory System"
echo "📝 Conversation ID: $CONV_ID"
echo "=" | head -c 80 && echo

# Test 1: Ask about creating hello world
echo ""
echo "TEST 1: Create hello world program"
echo "=" | head -c 80 && echo
curl -X POST http://127.0.0.1:8787/api/navi/chat/autonomous \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"Create a simple Python hello world program that prints 'Hello, World!'\",
    \"conversation_id\": \"$CONV_ID\",
    \"workspace_path\": \"$(pwd)\",
    \"run_verification\": false,
    \"model\": \"gpt-4o-mini\"
  }" 2>&1 | grep -E 'data: \{' | head -20

sleep 3

# Test 2: Reference the first request
echo ""
echo ""
echo "TEST 2: Reference first request - TESTING MEMORY"
echo "=" | head -c 80 && echo
curl -X POST http://127.0.0.1:8787/api/navi/chat/autonomous \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"What was the message in the hello world program we just created?\",
    \"conversation_id\": \"$CONV_ID\",
    \"workspace_path\": \"$(pwd)\",
    \"run_verification\": false,
    \"model\": \"gpt-4o-mini\"
  }" 2>&1 | grep -E 'data: \{' | head -20

sleep 2

# Check database
echo ""
echo ""
echo "DATABASE VERIFICATION:"
echo "=" | head -c 80 && echo
python3 -c "
import sys
from backend.database.session import get_db
from sqlalchemy import text

conv_id = sys.argv[1]
db = next(get_db())

# Check conversation using bind parameters (prevents SQL injection)
result = db.execute(
    text('SELECT id, title FROM navi_conversations WHERE id = :conv_id'),
    {'conv_id': conv_id}
)
conv = result.first()
if conv:
    print(f'✅ Conversation found: {conv[0]}')
    print(f'   Title: {conv[1]}')
else:
    print('❌ Conversation NOT found in database')

# Check messages using bind parameters
result = db.execute(
    text('SELECT COUNT(*) FROM navi_messages WHERE conversation_id = :conv_id'),
    {'conv_id': conv_id}
)
count = result.scalar()
print(f'📝 Messages in conversation: {count}')

if count >= 2:
    print('✅ Memory persistence WORKING!')
else:
    print('❌ Memory persistence FAILED - expected at least 2 messages')
" "$CONV_ID"

echo ""
echo "🎊 Memory test complete!"
echo "Conversation ID for manual verification: $CONV_ID"
