"""Search and indexing constants shared across modules"""

# Reindexing limits and thresholds
# MAX_CHANNELS_PER_SYNC: Limit the number of Slack channels processed per sync to avoid
# hitting Slack API rate limits and to keep memory usage manageable. Adjust as needed
# based on observed performance and Slack API constraints.
# Rationale / tuning notes:
#  - Slack rate limits: Workspaces commonly encounter per-method and per-token limits.
#    Keeping the default low (20) helps avoid history-listing spikes when multiple
#    org-wide syncs run concurrently or when many channels have long histories.
#    If you operate on a higher API tier or have coordinated sync scheduling, this
#    value can be safely increased.
#  - Memory usage: Each channel's fetched history and parsing can consume memory
#    (depends on message density and attachments). A conservative estimate is ~1-3MB
#    of transient memory per channel; 20 channels keeps peak usage modest on small
#    instances. Measure in your environment and lower if you see memory pressure.
#  - Operational guidance: If you see Slack rate-limit errors, reduce this value or
#    increase sync spacing; if you have ample memory and higher API allowance, raise it.
MAX_CHANNELS_PER_SYNC = 20  # Slack channels per sync operation
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
# Rationale: HTML markup typically adds 50-300% overhead compared to plain text.
# Common tags like <div>, <span>, <a href="...">, <p>, etc. add significant bytes.
# Confluence pages with heavy markup (tables, nested divs, inline styles) can exceed 3x ratio.
# Example: "Hello World" (11 chars) as '<p class="text">Hello World</p>' is 36 chars (3.3x).
# A conservative multiplier of 3 provides robust coverage:
#  - Handles typical Confluence pages (averaging 1.5-2.5x markup-to-text ratio)
#  - Protects against heavy markup scenarios (tables, nested divs) reaching 3-4x
#  - Reduces BeautifulSoup parsing time for large documents by pre-truncating
#  - Ensures we extract MAX_CONTENT_LENGTH chars of text after tag removal
# Trade-off: Slightly more HTML parsed than needed for simple pages, but avoids truncating
# text content prematurely on complex pages. Adjust down to 2.5 if memory is constrained.
HTML_OVERHEAD_MULTIPLIER = 3
