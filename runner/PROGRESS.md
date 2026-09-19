# Public outline and native page previews

Use task-local public-progress.py with the provided Python. Only explicit public
records reach the site; raw assistant messages and research notes are not published.

1. During research publish a concise factual note in the PPT language:
   python public-progress.py note --phase research --summary "..." --next "..."
2. Finish substantive outline.json (see the skill's content reference), then run:
   python public-progress.py outline
   The site keeps its sections, titles and summaries visible before images exist.
3. Build native pages in order. Publish a short building note with --slide N,
   then render and publish that actual page:
   python public-progress.py render --workspace PATH --slide N
   Open the returned PNG, repair/rerender before the next page. Do not publish
   review-state copies as actual deck pages. The host replaces final previews with
   independently verified final renders.
4. Republish outline.json whenever page content/order changes. Previews affected
   by a content change are cleared until their new native render arrives.
5. The host runs independent content and visual reviews after the author draft.
   Repair the actual findings, update outline/preview and export a fresh artifact.
   Do not label self-review as independent or static images as playback checks.

Provide meaningful updates during long work, roughly every 45–60 seconds when
there is new information. No invented completion percentages, repeated filler,
commands, raw logs, local paths, credentials or hidden reasoning. Publishing the
outline does not pause work for approval. Temporary transport failure alone must
not invalidate a usable deck; local public records remain available for retry.


For new decks, request.json pages is the final resolved total, including title and
closing slides. Use that exact count throughout outline, previews and delivery.
The website resolves an explicit brief total before the fallback numeric input.
Page indices support 1–50. Existing-deck edits keep task-dependent scope.
