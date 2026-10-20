# Worker presence and renderer readiness

At 13:04 on 2026-10-20, the actual worker process was alive, Amphetamine and the sleep guard were active, Docker was responding, and the website was reachable. Queue admission had stopped on `renderer_image_missing`. Docker listed the expected image and accepted its image ID and qualified reference while intermittently rejecting its short name. A direct container run and a complete isolated PPTX-to-PDF/PNG render subsequently succeeded. This incident was not a worker process exit.

The readiness gate exposed a separate presence bug: blocking queue claims also stopped the only idle worker heartbeat, so the website's 90-second online window expired. The login supervisor correctly saw a live process and did not restart it.

Changes:

- Bounded local image inspection retries the equivalent qualified reference after a short-name failure, in both runner and login watchdog. No pull/build or paid model test.
- A separate 20-second worker heartbeat continues independently of queue admission and available execution slots. Readiness checks are serialized across the queue and heartbeat threads.
- Authenticated worker heartbeat updates only the worker record, with empty execution capabilities while dependencies are unavailable. It returns before stale-job updates and lease creation. Default claims retain legacy behavior.
- Network errors in the service heartbeat are logged safely and retried by the next pulse; they do not terminate the task supervisor.

Validation: nine renderer/presence unit tests, four watchdog tests, three queue supervisor tests, ten production bridge tests, and the website's real-route SQLite backend suite passed. Regression fixtures verify that blocked presence never claims queued work, expires stale running work, changes task leases or consumes admission quota. Production v39 acknowledged the new heartbeat with no job payload. A real isolated render produced PDF and PNG successfully. A graceful handoff was staged while the existing 15-page task continued; no active task was force-stopped or requeued by this repair.
