import json
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pptx-agent/skills/pptx/scripts'))
from pptx_core.common import atomic_json
from pptx_core.package import Workspace,unpack
from recovery_workspace import relocate_task,digest,resolve_delivery


class RecoveryWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name).resolve()
        self.old=self.base/'old-task';self.old.mkdir();self.new=self.base/'new-task'
        self.ws=unpack(ROOT/'pptx-agent/skills/pptx/assets/blank.pptx',self.old/'.pptx-agent')
        native=self.ws.home/'renders/native';native.mkdir();(native/'page.png').write_bytes(b'owned test image');(native/'deck.pdf').write_bytes(b'%PDF-1.7 test receipt')
        exported=self.old/'finished.pptx';shutil.copyfile(self.ws.home/'original.pptx',exported)
        capture=self.ws.home/'interactive/renders/example';capture.mkdir(parents=True);(capture/'initial.png').write_bytes(b'owned test image')
        scene=self.ws.home/'interactive/deck/scenes/example.json';atomic_json(scene,{'schemaVersion':1,'id':'example'})
        atomic_json(self.ws.home/'interactive/deck/bundle.json',{'scenes':{'example':{'path':'scenes/example.json','sha256':digest(scene)}}})
        report={'ok':True,'runtime_verified':True,'testCount':1,'sceneId':'example','specHash':digest(scene),'directory':str(capture),'captures':['initial.png'],'explanation':'Keep this literal reference '+str(self.old)}
        atomic_json(capture/'report.json',report);atomic_json(self.ws.home/'interactive/tests/example.json',report)
        self.ws.state.update(latest_output=str(exported),last_render={'ok':True,'source_hash':digest(exported),'pages':[str(native/'page.png')],'pdf':str(native/'deck.pdf')},latest_interactive_render=report)
        self.ws.save();self.state_before=(self.ws.home/'state.json').read_bytes()
        shutil.copytree(self.old,self.new);self.home=self.new/self.ws.home.relative_to(self.old)
        self.before_old=self.files(self.old)

    def tearDown(self):self.temp.cleanup()

    def files(self,path):return {p.relative_to(path).as_posix():digest(p) for p in path.rglob('*') if p.is_file()}

    def test_real_workspace_opens_after_targeted_relocation_and_originals_remain_unchanged(self):
        result=relocate_task(self.old,self.new,{'plugin':str(ROOT/'pptx-agent')})
        restored=Workspace(self.home);restored.check_original()
        self.assertEqual(result['workspace_count'],1)
        self.assertEqual(result['workspaces'][str(self.ws.root)],str(restored.root))
        self.assertEqual(restored.state['source'],str(self.home/'original.pptx'))
        self.assertEqual(restored.state['latest_output'],str(self.new/'finished.pptx'))
        self.assertTrue(all(Path(p).is_file() for p in restored.state['last_render']['pages']))
        receipt=json.loads((self.home/'interactive/tests/example.json').read_text())
        self.assertTrue(receipt['runtime_verified']);self.assertTrue(receipt['directory'].startswith(str(self.new)))
        self.assertEqual(receipt['explanation'],'Keep this literal reference '+str(self.old))
        backup=Path(result['backup'])/self.ws.home.relative_to(self.old)/'state.json'
        self.assertEqual(backup.read_bytes(),self.state_before)
        self.assertEqual(self.files(self.old),self.before_old)
        again=relocate_task(self.old,self.new,{})
        self.assertEqual(again['changed'],0);self.assertIsNone(again['backup'])

    def test_missing_captures_and_exports_invalidate_receipts_without_deleting_history(self):
        broken=self.home/'interactive/tests/example.json';value=json.loads(broken.read_text());value['captures']=['missing.png'];atomic_json(broken,value)
        state=json.loads((self.home/'state.json').read_text());state['latest_output']=str(self.old/'missing.pptx');state['last_render']['pdf']=str(self.old/'missing.pdf');state['latest_interactive_render']['captures']=['missing.png'];atomic_json(self.home/'state.json',state)
        result=relocate_task(self.old,self.new,{})
        restored=Workspace(self.home)
        self.assertIsNone(restored.state['latest_output']);self.assertIsNone(restored.state['last_render']);self.assertIsNone(restored.state['latest_interactive_render'])
        self.assertFalse(json.loads(broken.read_text())['runtime_verified'])
        self.assertGreaterEqual(len(result['invalidated']),3)
        self.assertTrue((self.home/'interactive/renders/example/initial.png').is_file())

    def test_tampered_protected_copy_rejects_before_any_active_json_write(self):
        original=self.home/'original.pptx';original.chmod(0o644)
        with original.open('ab') as stream:stream.write(b'tampered restored test copy')
        state=(self.home/'state.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'original hash mismatch'):relocate_task(self.old,self.new,{})
        self.assertEqual((self.home/'state.json').read_bytes(),state)
        self.assertFalse((self.new/'.recovery-relocation').exists())
        self.assertEqual(self.files(self.old),self.before_old)

    def test_external_report_paths_and_symlinks_do_not_escape_recovery_scope(self):
        path=self.home/'interactive/tests/example.json';value=json.loads(path.read_text());value['directory']=str(self.base/'outside');atomic_json(path,value)
        result=relocate_task(self.old,self.new,{})
        self.assertFalse(json.loads(path.read_text())['runtime_verified']);self.assertTrue(result['invalidated'])
        (self.new/'unsafe').symlink_to(self.old)
        with self.assertRaisesRegex(ValueError,'symlink'):relocate_task(self.old,self.new,{})

    def test_snapshot_history_and_unrelated_json_are_not_rewritten(self):
        snapshot=self.home/'snapshots/frozen';snapshot.mkdir(parents=True)
        frozen={'interactive_state':{'directory':str(self.old/'receipt')}};atomic_json(snapshot/'snapshot.json',frozen)
        note=self.new/'author-note.json';atomic_json(note,{'workspace':str(self.ws.root),'text':str(self.old)})
        before=digest(snapshot/'snapshot.json');note_before=digest(note)
        relocate_task(self.old,self.new,{})
        self.assertEqual(digest(snapshot/'snapshot.json'),before);self.assertEqual(digest(note),note_before)

    def test_completed_delivery_receipts_survive_multiple_restorations(self):
        from durable import Journal
        receipt={'path':str(self.old/'finished.pptx'),'workspace':str(self.ws.root),'note':str(self.old)}
        atomic_json(self.old/'delivery.json',receipt)
        with Journal(self.base/'journal','restore-delivery',plugin_version='0.2.0') as journal:
            journal.begin_phase('author',self.old)
            journal.complete_phase('author',self.old,artifacts=['delivery.json','finished.pptx'],next_phase='review')
            journal.checkpoint(self.old)
            current=self.old
            for number in (1,2):
                target=self.base/('restored-'+str(number))
                journal.recover(target,plugin_version='0.2.0',recovery_id='attempt-'+str(number))
                relocate_task(current,target)
                delivery=resolve_delivery(receipt,target,journal.state['recoveries'].values())
                self.assertEqual(delivery['path'],str(target/'finished.pptx'))
                self.assertEqual(delivery['workspace'],str(target/self.ws.root.relative_to(self.old)))
                self.assertEqual(delivery['note'],str(self.old))
                self.assertEqual(json.loads((target/'delivery.json').read_text()),receipt)
                self.assertTrue(journal.can_reuse('author',target))
                journal.checkpoint(target);current=target
        self.assertEqual(json.loads((self.old/'delivery.json').read_text()),receipt)

    def test_delivery_resolver_rejects_unrecorded_roots_and_traversal(self):
        for path in (str(self.old/'finished.pptx'),'../old-task/finished.pptx',str(self.new/'../old-task/finished.pptx')):
            with self.assertRaises(ValueError):resolve_delivery({'path':path},self.new)
        receipt={'path':'finished.pptx','workspace':str(self.home/'workspace')}
        self.assertEqual(resolve_delivery(receipt,self.new)['path'],str(self.new/'finished.pptx'))

    def test_supervisor_recovery_under_aliased_temp_parent_keeps_native_render_scoped(self):
        import runner
        from durable import Journal

        real_parent=self.base/'real-parent';real_parent.mkdir()
        (real_parent/'scratch').mkdir()
        alias=self.base/'temporary-alias';alias.symlink_to(real_parent,target_is_directory=True)
        temporary_alias=alias/'scratch'
        task={'id':str(uuid.uuid4()),'lease':str(uuid.uuid4())}
        state_root=self.base/'state'
        cfg={'state_directory':str(state_root),'plugin_version':'0.2.0',
             'plugin':str(ROOT/'pptx-agent'),'token':'synthetic-recovery-test-token'}
        with Journal(state_root,task['id'],plugin_version='0.2.0') as journal:
            journal.begin_phase('author',self.old)
            journal.checkpoint(self.old,reason='before-interruption')

        def continue_recovered(config,actual_task,lease,job,journal,plan):
            # This assertion exercises the supervisor call site, not only the
            # relocation helper which already canonicalizes its own copy.
            self.assertEqual(job,job.resolve())
            self.assertEqual(job.parent,real_parent/'scratch')
            self.assertEqual(str(job),journal.state['workspace'])
            source=job/'draft.pptx';source.write_bytes(b'PK-owned-render-fixture')
            destination=job/'rendered';destination.mkdir()
            queue=job/'render-requests'
            identifier='a'*32
            request={'args':['--headless','--convert-to','pdf','--outdir',str(destination),str(source.resolve())]}
            (queue/(identifier+'.request.json')).write_text(json.dumps(request))

            def convert(command,**kwargs):
                self.assertIn('type=bind,source='+str(job)+',target=/work',command)
                self.assertEqual(command[-1],'/work/draft.pptx')
                self.assertIn('/work/rendered',command)
                (destination/'draft.pdf').write_bytes(b'%PDF-scoped-fixture')
                return SimpleNamespace(returncode=0,stdout='rendered',stderr='')

            with patch.object(runner.subprocess,'run',side_effect=convert) as docker:
                runner.render_requests(job)
                self.assertEqual(docker.call_count,1)
            reply=json.loads((queue/(identifier+'.reply.json')).read_text())
            self.assertEqual(reply['returncode'],0)
            self.assertTrue((destination/'draft.pdf').is_file())

            outside=self.base/'outside.pptx';outside.write_bytes(b'PK-outside-fixture')
            for index,args in enumerate([
                [*request['args'][:-1],str(outside)],
                ['--headless','--convert-to','pdf','--outdir',str(self.base),str(source)],
            ]):
                identifier=str(index+1)*32
                (queue/(identifier+'.request.json')).write_text(json.dumps({'args':args}))
                with patch.object(runner.subprocess,'run') as docker:
                    runner.render_requests(job);docker.assert_not_called()
                self.assertNotEqual(json.loads((queue/(identifier+'.reply.json')).read_text())['returncode'],0)
            return 'continued-with-scoped-native-render'

        with patch.object(runner.tempfile,'gettempdir',return_value=str(temporary_alias)),\
             patch.object(runner,'_run_job_locked',side_effect=continue_recovered):
            result=runner._run_job(cfg,task,SimpleNamespace())
        self.assertEqual(result,'continued-with-scoped-native-render')
        self.assertEqual(self.files(self.old),self.before_old)


if __name__=='__main__':unittest.main()
