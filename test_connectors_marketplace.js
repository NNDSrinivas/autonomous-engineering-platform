// Test script to verify connectors marketplace functionality
// Run this in browser developer console when the NAVI panel is open

console.log('🧪 Testing Connectors Marketplace...');

// Check if ConnectorsMarketplace class exists
if (typeof window.ConnectorsMarketplace !== 'undefined') {
    console.log('✅ ConnectorsMarketplace class found');
} else {
    console.error('❌ ConnectorsMarketplace class not found');
    console.log('Available window properties:', Object.keys(window).filter(k => k.includes('Connector') || k.includes('AEP')));
}

// Check if connectors root element exists
const connectorsRoot = document.getElementById('aep-connectors-root');
if (connectorsRoot) {
    console.log('✅ Connectors root element found');
} else {
    console.error('❌ Connectors root element not found');
}

// Check if marketplace instance exists
if (typeof window.connectorsMarketplace !== 'undefined') {
    console.log('✅ Marketplace instance found');

    // Test opening/closing
    console.log('🧪 Testing marketplace toggle...');
    window.connectorsMarketplace.open();

    setTimeout(() => {
        console.log('🧪 Testing marketplace close...');
        window.connectorsMarketplace.close();
    }, 2000);

} else {
    console.error('❌ Marketplace instance not found');
}

// Check for backend URL configuration
if (window.AEP_BACKEND_BASE_URL) {
    console.log('✅ Backend URL configured:', window.AEP_BACKEND_BASE_URL);
} else {
    console.warn('⚠️ Backend URL not configured');
}

// Test connectors button click
const connectorsBtn = document.querySelector('[data-action="connectors"]');
if (connectorsBtn) {
    console.log('✅ Connectors button found');
    console.log('🧪 Click the 🔌 button to test marketplace...');
} else {
    console.error('❌ Connectors button not found');
}

console.log('🧪 Test complete! Check the results above.');