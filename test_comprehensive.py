#!/usr/bin/env python3

import requests
import json


def test_comprehensive_analysis():
    """Test the comprehensive analysis with longer timeout"""

    print("Testing comprehensive analysis endpoint...")
    url = "http://localhost:8787/api/navi/analyze-changes"
    params = {
        "workspace_root": "/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform"
    }

    print(f"URL: {url}")
    print(f"Params: {params}")

    try:
        # Use streaming with longer timeout (POST request)
        response = requests.post(
            url, json=params, stream=True, timeout=120
        )  # 2 minutes
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")

        if response.status_code == 200:
            print("\n--- Streaming Response (showing all data) ---")

            line_count = 0
            result_data = None

            for line in response.iter_lines(decode_unicode=True):
                line_count += 1

                if line.strip() == "":
                    continue

                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    try:
                        data = json.loads(data_str)
                        print(f"[{line_count}] {data}")

                        # Store the final result
                        if data.get("type") == "result":
                            result_data = data

                    except json.JSONDecodeError as e:
                        print(f"[{line_count}] JSON decode error: {e}")
                        print(f"[{line_count}] Raw data: {data_str[:200]}...")

                # Stop after getting result or if too many lines
                if result_data or line_count > 100:
                    break

            # Show final result summary if we got one
            if result_data:
                print("\n=== COMPREHENSIVE ANALYSIS RESULT ===")
                result = result_data.get("result", {})

                print(f"Analysis Summary: {result.get('summary', 'N/A')}")
                print(f"Files Analyzed: {len(result.get('files', []))}")

                # Show sample file analysis
                files = result.get("files", [])
                if files:
                    sample_file = files[0]
                    print(f"\nSample Analysis ({sample_file.get('path', 'N/A')}):")
                    print(f"  Issues Found: {len(sample_file.get('issues', []))}")
                    print(f"  Quality Score: {sample_file.get('quality_score', 'N/A')}")

                    # Show first issue if available
                    issues = sample_file.get("issues", [])
                    if issues:
                        issue = issues[0]
                        print(
                            f"  Sample Issue: {issue.get('type', 'N/A')} - {issue.get('message', 'N/A')}"
                        )

                print(f"\nTotal Analysis Lines: {line_count}")
                return True
            else:
                print(
                    f"\nNo final result received. Total lines processed: {line_count}"
                )
                return False

        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return False

    except requests.exceptions.Timeout:
        print("Request timed out after 2 minutes")
        return False
    except Exception as e:
        print(f"Request failed: {e}")
        return False


if __name__ == "__main__":
    success = test_comprehensive_analysis()
    if success:
        print("\n✅ Comprehensive analysis completed successfully!")
    else:
        print("\n❌ Comprehensive analysis failed or incomplete")
