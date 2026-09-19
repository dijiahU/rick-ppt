import threading
import unittest
import sqlite3
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from queue_pool import serve

class PoolTest(unittest.TestCase):
    def test_simultaneous_sql_claims_never_exceed_three(self):
        source=(Path(__file__).resolve().parent.parent/'website/lib/queries.ts').read_text()
        query=source.split('export const CLAIM_JOB = `',1)[1].split('`',1)[0]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'queue.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE jobs(id TEXT,status TEXT,lease TEXT,updated_at INTEGER,created_at INTEGER,title TEXT,brief TEXT,pages INTEGER,style TEXT,language TEXT,attachments TEXT)')
                db.executemany("INSERT INTO jobs(id,status,created_at) VALUES (?,'queued',?)",[(str(i),i) for i in range(20)])
            barrier=threading.Barrier(12)
            def claim(i):
                with sqlite3.connect(path,timeout=10) as db:
                    barrier.wait(3)
                    return db.execute(query,(str(i),1)).fetchone()
            with ThreadPoolExecutor(max_workers=12) as pool:rows=list(pool.map(claim,range(12)))
            accepted=[row for row in rows if row]
            self.assertEqual(len(accepted),3);self.assertEqual(len({row[0] for row in accepted}),3)

    def test_three_overlap_and_fourth_waits_then_refills(self):
        stop=threading.Event();release=[threading.Event() for _ in range(4)]
        started=[threading.Event() for _ in range(4)];lock=threading.Lock()
        claimed=[];completed=[];active=0;peak=0;errors=[]
        def claim():
            with lock:
                if len(claimed)==4:return None
                i=len(claimed);claimed.append(i);return {'id':i}
        def execute(task):
            nonlocal active,peak
            i=task['id']
            with lock:active+=1;peak=max(peak,active)
            started[i].set()
            if not release[i].wait(5):raise TimeoutError('test release')
            with lock:active-=1;completed.append(i)
        supervisor=threading.Thread(target=serve,args=(claim,execute,stop,errors.append),kwargs={'poll_seconds':.01})
        supervisor.start()
        try:
            for event in started[:3]:self.assertTrue(event.wait(2))
            self.assertFalse(started[3].is_set());self.assertEqual(len(claimed),3)
            release[0].set();self.assertTrue(started[3].wait(2))
            stop.set();self.assertTrue(supervisor.is_alive())
        finally:
            stop.set()
            for event in release:event.set()
            supervisor.join(5)
        self.assertFalse(supervisor.is_alive());self.assertEqual(peak,3)
        self.assertEqual(sorted(completed),[0,1,2,3]);self.assertEqual(errors,[])

    def test_once_failure_and_inflight_claim_drain(self):
        stop=threading.Event();seen=[];errors=[]
        def claim():stop.set();return {'id':'leased'}
        def execute(task):seen.append(task['id']);raise ValueError('test')
        serve(claim,execute,stop,errors.append,once=True)
        self.assertEqual(seen,['leased']);self.assertEqual(len(errors),1)

if __name__=='__main__':unittest.main()
