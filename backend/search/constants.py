"""Search and indexing constants shared across modules"""

# Reindexing limits and thresholds
MAX_CHANNELS_PER_SYNC = 20  # Slack channels to sync per request
SLACK_HISTORY_LIMIT = 300  # Messages per channel per sync
CONFLUENCE_PAGE_LIMIT = 200  # Pages to fetch per sync
MAX_CONTENT_LENGTH = 200000  # Max characters for text content
MAX_MEETINGS_PER_SYNC = 1000  # Meeting records to sync per request
# HTML overhead multiplier for pre-parsing truncation
# Rationale: HTML markup typically adds 50-150% overhead compared to plain text.
# Common tags like <div>, <span>, <a href="...">, <p>, etc. add significant bytes.
# Example: "Hello World" (11 chars) as '<p class="text">Hello World</p>' is 36 chars (3.3x).
# A multiplier of 2 provides a reasonable balance:
#  - Captures most content without processing unnecessarily large documents
#  - Reduces BeautifulSoup parsing time for large Confluence pages
#  - Still extracts MAX_CONTENT_LENGTH chars of text after tag removal
# Tested with typical Confluence pages averaging 1.5-2.5x markup-to-text ratio.
HTML_OVERHEAD_MULTIPLIER = 2
