#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Read the compiled bundle
const bundlePath = path.join(__dirname, 'extensions/vscode-aep/dist/webview/panel.js');

console.log('🔍 Analyzing compiled React bundle...');
console.log('📁 Bundle path:', bundlePath);

try {
    const bundleContent = fs.readFileSync(bundlePath, 'utf8');
    console.log('📊 Bundle size:', bundleContent.length, 'characters');
    
    // Test for key components and functions
    const tests = [
        {
            name: 'UIProvider export',
            pattern: /UIProvider/g,
            critical: true
        },
        {
            name: 'ADD_PLAN reducer case',
            pattern: /ADD_PLAN.*REACHED|REACHED.*ADD_PLAN/g,
            critical: true
        },
        {
            name: 'App function logs',
            pattern: /ENTRY.*App.*function|App.*function.*called/g,
            critical: true
        },
        {
            name: 'Event router dispatch',
            pattern: /navi\.assistant\.plan/g,
            critical: false
        },
        {
            name: 'React useReducer',
            pattern: /useReducer/g,
            critical: true
        },
        {
            name: 'PlanRenderer component',
            pattern: /PlanRenderer/g,
            critical: false
        },
        {
            name: 'data-plan-message attribute',
            pattern: /data-plan-message/g,
            critical: false
        }
    ];
    
    console.log('\n🧪 Running tests...\n');
    
    let passedTests = 0;
    let criticalFailures = 0;
    
    tests.forEach((test, index) => {
        const matches = bundleContent.match(test.pattern);
        const passed = matches && matches.length > 0;
        
        if (passed) {
            console.log(`✅ ${test.name}: FOUND (${matches.length} matches)`);
            passedTests++;
        } else {
            console.log(`❌ ${test.name}: NOT FOUND${test.critical ? ' (CRITICAL)' : ''}`);
            if (test.critical) criticalFailures++;
        }
    });
    
    console.log(`\n📈 Results: ${passedTests}/${tests.length} tests passed`);
    
    if (criticalFailures > 0) {
        console.log(`🚨 ${criticalFailures} critical failures detected!`);
        console.log('💡 This suggests the build system is still not compiling all components properly.');
        
        // Specific analysis for the build issue
        console.log('\n🔬 Build System Analysis:');
        
        const hasUIProvider = bundleContent.includes('UIProvider');
        const hasAppFunction = bundleContent.includes('ENTRY') && bundleContent.includes('App');
        const hasReducer = bundleContent.includes('ADD_PLAN') && bundleContent.includes('REACHED');
        
        console.log(`  • UIProvider present: ${hasUIProvider}`);
        console.log(`  • App function logs present: ${hasAppFunction}`);
        console.log(`  • ADD_PLAN reducer logs present: ${hasReducer}`);
        
        if (hasUIProvider && !hasAppFunction && !hasReducer) {
            console.log('\n💭 Hypothesis: Selective compilation issue persists');
            console.log('   Some components are updating while others remain stale.');
        }
        
        return 1; // Exit code for failure
    } else {
        console.log('🎉 All critical tests passed! React state management should work.');
        return 0;
    }
    
} catch (error) {
    console.error('❌ Error reading bundle:', error.message);
    return 1;
}