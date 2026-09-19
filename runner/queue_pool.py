"""One queue supervisor, at most three isolated task executions; drain on stop."""
from concurrent.futures import ThreadPoolExecutor


def serve(claim, execute, stop, on_error, *, capacity=3, poll_seconds=2, once=False):
    if not isinstance(capacity, int) or not 1 <= capacity <= 3:
        raise ValueError('Capacity must be 1..3')
    active=set()
    with ThreadPoolExecutor(max_workers=capacity,thread_name_prefix='pptx-job') as pool:
        while not stop.is_set():
            completed={f for f in active if f.done()}
            active-=completed
            for future in completed:
                try:future.result()
                except Exception as error:on_error(error)
            if len(active)<capacity:
                task=None
                try:
                    task=claim()
                    # A successful in-flight claim must be serviced even if stop
                    # arrived during its HTTP request. Never orphan a leased job.
                    if task:active.add(pool.submit(execute,task))
                except Exception as error:on_error(error)
                if once:break
                if task:
                    continue
            stop.wait(poll_seconds)
        # Executor context waits for active jobs without cancelling any task.
        for future in active:
            try:future.result()
            except Exception as error:on_error(error)
