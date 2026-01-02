#!/usr/bin/env python3
"""Test the simple streaming endpoint"""
import requests

url = "http://localhost:8787/api/navi/test-stream"
print(f"Testing: {url}")

try:
    response = requests.get(url, stream=True, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        for i, line in enumerate(response.iter_lines(decode_unicode=True)):
            print(f"[{i}] {line}")
            if i > 10:  # Limit output
                break
    else:
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"Error: {e}")