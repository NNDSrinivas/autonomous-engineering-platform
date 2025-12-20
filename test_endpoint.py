#!/usr/bin/env python3
"""
Simple test script to verify the analyze-changes endpoint returns real analysis
"""
import requests
import json
import os

def test_analyze_endpoint():
    url = "http://localhost:8787/api/navi/analyze-changes"
    headers = {
        "Content-Type": "application/json",
        "X-Org-Id": "org_aep_platform_4538597546e6fec6"
    }
    
    workspace_root = "/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform"
    
    # Send workspace_root as query parameter instead of JSON body
    params = {
        "workspace_root": workspace_root
    }
    
    print("Testing analyze-changes endpoint...")
    print(f"URL: {url}")
    print(f"Params: {params}")
    
    try:
        # Test with streaming - shorter timeout
        response = requests.post(url, headers=headers, params=params, stream=True, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("\n--- Streaming Response ---")
            line_count = 0
            success = False
            for line in response.iter_lines(decode_unicode=True):
                line_count += 1
                print(f"[{line_count}] Raw line: {repr(line)}")
                
                if line and line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])  # Remove "data: " prefix
                        print(f"[{line_count}] Parsed: {data}")
                        
                        # Check if it's real analysis (not mock)
                        if data.get('type') == 'review':
                            payload_data = json.loads(data.get('payload', '{}'))
                            if 'files' in payload_data:
                                files = payload_data['files']
                                print(f"\n✅ REAL ANALYSIS DETECTED: {len(files)} files analyzed")
                                for file_info in files[:2]:  # Show first 2 files
                                    issues = file_info.get('issues', [])
                                    print(f"  📄 {file_info.get('path')}: {len(issues)} issues")
                                    if issues:
                                        print(f"    Sample issue: {issues[0].get('title', 'No title')}")
                                success = True
                                break
                        
                        # Stop after we see completion or 30 messages
                        if data.get('type') == 'complete' or line_count > 30:
                            print("... stopping after completion or 30 messages")
                            success = True
                            break
                    except json.JSONDecodeError as e:
                        print(f"[{line_count}] JSON decode error: {e}")
                elif line:
                    print(f"[{line_count}] Non-data line: {line}")
                
                # Timeout after 50 lines to prevent infinite hanging
                if line_count > 50:
                    print("... stopping after 50 lines")
                    break
            
            if success:
                print(f"\n✅ Test completed successfully! Got {line_count} lines")
            else:
                print(f"\n⚠️ Test timed out after {line_count} lines")
                        
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_analyze_endpoint()