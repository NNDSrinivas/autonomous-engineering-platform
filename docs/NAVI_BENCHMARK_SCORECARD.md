# NAVI Benchmark Scorecard

Generated: 2026-02-26 03:51:25

## Summary

- Tasks: 6
- Passed: 6
- Failed: 0
- Total Duration (s): 32.73

## Results

| Task | Label | Success | Timed Out | Duration (s) | Command |
| --- | --- | --- | --- | --- | --- |
| small | Small task | True | False | 2.35 | `python3 -m pytest backend/tests/test_navi_comprehensive.py::TestFileOperations::test_read_file_content backend/tests/test_navi_comprehensive.py::TestCodeAnalysis::test_detect_python_print_statements -q` |
| medium | Medium task | True | False | 1.83 | `python3 -m pytest backend/tests/test_navi_comprehensive.py::TestCodeAnalysis::test_analyze_large_repository_structure -q` |
| semi_medium | Semi‑medium task | True | False | 9.89 | `python3 -m pytest backend/tests/test_navi_api_integration.py::TestCodeReviewEndpoints::test_review_working_tree_endpoint -q` |
| long | Long task | True | False | 7.76 | `python3 -m pytest backend/tests/test_navi_api_integration.py -q` |
| complex | Complex task | True | False | 8.99 | `python3 -m pytest backend/tests/test_navi_comprehensive.py backend/tests/test_navi_api_integration.py -q` |
| staging_smoke | Staging smoke | True | False | 1.91 | `python3 -m pytest backend/tests/test_staging_smoke.py -q` |

## Notes

- Durations are wall-clock time for each benchmark task.
- Use this scorecard to track regressions/improvements over time.
