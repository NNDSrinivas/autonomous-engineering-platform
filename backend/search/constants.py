"""Search and indexing constants shared across modules"""

# Reindexing limits and thresholds
# MAX_CHANNELS_PER_SYNC: Limit the number of Slack channels processed per sync to avoid
# hitting Slack API rate limits and to keep memory usage manageable. Adjust as needed
# based on observed performance and Slack API constraints.
MAX_CHANNELS_PER_SYNC = 20  # Slack channels to sync per request
SLACK_HISTORY_LIMIT = 300  # Messages per channel per sync
CONFLUENCE_PAGE_LIMIT = 200  # Pages to fetch per sync
MAX_CONTENT_LENGTH = 200000  # Max characters for text content
# MAX_MEETINGS_PER_SYNC: Limit meeting records retrieved per sync operation to manage
# database query performance and memory usage. Each meeting includes summary JSON which
# can be several KB. At 1000 meetings with ~2KB summaries, this is ~2MB of data transferred
# from DB to application. The LIMIT clause combined with ORDER BY created_at DESC ensures
# recent meetings are prioritized. Adjust based on:
#  - Database query performance (lower if queries become slow)
#  - Memory constraints (lower for smaller instances)
#  - Meeting creation frequency (raise if org creates >1000 meetings between syncs)
MAX_MEETINGS_PER_SYNC = 1000  # Meeting records to sync per request
# HTML overhead multiplier for pre-parsing truncation
# Rationale: HTML markup typically adds 50-150% overhead compared to plain text.
# Common tags like <div>, <span>, <a href="...">, <p>, etc. add significant bytes.
# Example: "Hello World" (11 chars) as '<p class="text">Hello World</p>' is 36 chars (3.3x).
# A conservative multiplier of 2 provides a reasonable balance:
#  - Handles most typical Confluence pages (averaging 1.5-2.5x markup-to-text ratio)
#  - Protects against worst-case scenarios like the 3.3x example above
#  - Reduces BeautifulSoup parsing time for large documents
#  - Still extracts MAX_CONTENT_LENGTH chars of text after tag removal
HTML_OVERHEAD_MULTIPLIER = 2
