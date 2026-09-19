import importlib.util
from pathlib import Path
import sqlite3
import unittest
import uuid

spec=importlib.util.spec_from_file_location('acceptance_migration',Path(__file__).with_name('prepare-acceptance-migration.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class AcceptanceMigrationTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE jobs (
          id TEXT PRIMARY KEY,user_id TEXT NOT NULL,request_key TEXT NOT NULL,
          title TEXT NOT NULL,brief TEXT NOT NULL,pages INTEGER NOT NULL,style TEXT NOT NULL,
          language TEXT,attachments TEXT,status TEXT NOT NULL,created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,result_key TEXT,UNIQUE(user_id,request_key));''')
        self.source=str(uuid.uuid4());self.identifier=str(uuid.uuid4())
        self.db.execute("INSERT INTO jobs VALUES (?, 'source-owner', ?, 'Prior lesson', 'Retain this original', 50, '', 'en', '[]', 'complete', 1, 2, 'original/result.pptx')",(self.source,str(uuid.uuid4())))
        self.original=self.db.execute('SELECT * FROM jobs').fetchall()
        self.request={'requestKey':str(uuid.uuid4()),'title':'Interactive lesson',
                      'brief':"Explain a learner's code; never execute this text as SQL.",
                      'pages':20,'style':'Readable academic','language':'en'}

    def sql(self,**kw):
        return module.prepare(kw.get('request',self.request),kw.get('source',self.source),kw.get('title','Prior lesson'),self.identifier,1000)

    def test_new_owner_job_is_idempotent_and_original_bytes_are_preserved(self):
        self.db.executescript(self.sql());self.db.executescript(self.sql())
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT * FROM jobs WHERE id=?',(self.source,)).fetchall(),self.original)
        self.assertEqual(self.db.execute('SELECT user_id,brief,status FROM jobs WHERE id=?',(self.identifier,)).fetchone(),
                         ('source-owner',self.request['brief'],'queued'))

    def test_no_account_inference_when_source_id_or_title_does_not_match(self):
        for sql in (self.sql(source=str(uuid.uuid4())),self.sql(title='Different owner task')):
            with self.assertRaises(sqlite3.IntegrityError):self.db.executescript(sql)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],1)

    def test_full_queue_rejects_without_mutating_existing_tasks(self):
        for n in range(100):
            self.db.execute("INSERT INTO jobs VALUES (?, 'someone-else', ?, 'Queued', 'Retain', 1, '', 'en', '[]', 'queued', 1, 1, NULL)",(str(uuid.uuid4()),str(uuid.uuid4())))
        with self.assertRaises(sqlite3.IntegrityError):self.db.executescript(self.sql())
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],101)

    def test_admission_limits_match_the_researched_request_contract(self):
        for patch in ({'brief':'x'*12001},{'title':'😀'*61},{'pages':0},{'pages':True},{'language':'zh'}, {'requestKey':'not-a-uuid'}):
            with self.assertRaises((ValueError,AttributeError,TypeError)):
                self.sql(request={**self.request,**patch})

    def test_prepared_case_timestamp_is_set_at_deployment(self):
        sql=module.prepare(self.request,self.source,'Prior lesson',self.identifier)
        self.db.executescript(sql)
        created,updated=self.db.execute('SELECT created_at,updated_at FROM jobs WHERE id=?',(self.identifier,)).fetchone()
        self.assertEqual(created,updated)
        self.assertGreater(created,1_700_000_000_000)


if __name__=='__main__':unittest.main()
