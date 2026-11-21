# Public outline and page previews

Use task-local public-progress.py with the provided Python. Only these explicit
records reach the website; notes and raw messages are not published.

1. During research publish short factual notes in the PPT language:
   python public-progress.py note --phase research --summary "..." --next "..."
2. After writing outline.json run `python public-progress.py outline`. Republish it
   whenever page content or order changes.
3. Build pages in order; after each page run
   `python public-progress.py render --workspace PATH --slide N`, open the PNG and
   fix it before the next page.
4. The host runs the independent reviews after the draft; repair the findings and
   export a fresh file.

Give a meaningful update roughly every 45–60 seconds of long work when there is
news. No invented percentages, filler, commands, logs, local paths, credentials or
hidden reasoning. Publishing the outline does not wait for approval.

request.json `pages` is the final total including title and closing slides (1–50);
use it for the outline, previews and delivery. Edits keep their own scope.
