# NAVI Benchmark Scorecard

Generated: 2026-05-05 04:05:42

## Summary

- Tasks: 6
- Passed: 6
- Failed: 0
- Total Duration (s): 31.64

## Results

| Task | Label | Success | Timed Out | Duration (s) | Command |
| --- | --- | --- | --- | --- | --- |
| small | Small task | True | False | 2.24 | `python3 -m pytest backend/tests/test_navi_comprehensive.py::TestFileOperations::test_read_file_content backend/tests/test_navi_comprehensive.py::TestCodeAnalysis::test_detect_python_print_statements -q` |
| medium | Medium task | True | False | 1.47 | `python3 -m pytest backend/tests/test_navi_comprehensive.py::TestCodeAnalysis::test_analyze_large_repository_structure -q` |
| semi_medium | Semi‑medium task | True | False | 10.01 | `python3 -m pytest backend/tests/test_navi_api_integration.py::TestCodeReviewEndpoints::test_review_working_tree_endpoint -q` |
| long | Long task | True | False | 7.9 | `python3 -m pytest backend/tests/test_navi_api_integration.py -q` |
| complex | Complex task | True | False | 8.12 | `python3 -m pytest backend/tests/test_navi_comprehensive.py backend/tests/test_navi_api_integration.py -q` |
| staging_smoke | Staging smoke | True | False | 1.9 | `python3 -m pytest backend/tests/test_staging_smoke.py -q` |

## Notes

- Durations are wall-clock time for each benchmark task.
- Use this scorecard to track regressions/improvements over time.
