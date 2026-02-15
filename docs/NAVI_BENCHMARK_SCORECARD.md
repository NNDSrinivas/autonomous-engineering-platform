# NAVI Benchmark Scorecard

Generated: 2026-02-15 03:54:24

## Summary

- Tasks: 5
- Passed: 5
- Failed: 0
- Total Duration (s): 27.08

## Results

| Task | Label | Success | Timed Out | Duration (s) | Command |
| --- | --- | --- | --- | --- | --- |
| small | Small task | True | False | 1.88 | `python3 -m pytest backend/tests/test_navi_comprehensive.py::TestFileOperations::test_read_file_content backend/tests/test_navi_comprehensive.py::TestCodeAnalysis::test_detect_python_print_statements -q` |
| medium | Medium task | True | False | 1.64 | `python3 -m pytest backend/tests/test_navi_comprehensive.py::TestCodeAnalysis::test_analyze_large_repository_structure -q` |
| semi_medium | Semi‑medium task | True | False | 8.9 | `python3 -m pytest backend/tests/test_navi_api_integration.py::TestCodeReviewEndpoints::test_review_working_tree_endpoint -q` |
| long | Long task | True | False | 7.28 | `python3 -m pytest backend/tests/test_navi_api_integration.py -q` |
| complex | Complex task | True | False | 7.38 | `python3 -m pytest backend/tests/test_navi_comprehensive.py backend/tests/test_navi_api_integration.py -q` |

## Notes

- Durations are wall-clock time for each benchmark task.
- Use this scorecard to track regressions/improvements over time.
