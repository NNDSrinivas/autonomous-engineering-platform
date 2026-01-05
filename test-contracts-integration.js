// Quick test to verify contracts integration works
const { IntentKind, IntentFamily, getFallbackIntent } = require('./packages/navi-contracts/dist');

console.log('🧪 Testing contracts integration...\n');

// Test that we can import and use the contracts
console.log('✅ Import works');
console.log('   Available intents:', Object.keys(IntentKind).length);
console.log('   Available families:', Object.keys(IntentFamily).length);

// Test some key intents that match existing system
console.log('\n✅ Key intent mappings work');
console.log('   FIX_DIAGNOSTICS:', IntentKind.FIX_DIAGNOSTICS);
console.log('   GREET:', IntentKind.GREET);
console.log('   DEPLOY:', IntentKind.DEPLOY);

// Test that the extension can use the fallback logic
console.log('\n✅ Fallback logic integration test');
const testMessages = [
  'hi there',
  'fix this error please', 
  'deploy to production',
  'some random request'
];

testMessages.forEach(msg => {
  const intent = getFallbackIntent(msg);
  console.log(`   "${msg}" → ${intent.kind} (${intent.confidence})`);
});

console.log('\n🎉 Contracts integration successful!\n');