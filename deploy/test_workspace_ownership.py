"""Stable ownership must not invalidate checkpoints between task commands."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

from linux_sandbox import own_workspace


@unittest.skipUnless(sys.platform=='linux' and os.geteuid()==0,'Linux host ownership test')
class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='pptx-owner-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.uid=723456789
        (self.root/'nested').mkdir();(self.root/'nested/data').write_bytes(b'preserved')

    def signatures(self):
        return {str(p.relative_to(self.root)):(p.stat().st_ctime_ns,p.stat().st_uid,p.stat().st_gid)
                for p in [self.root,*self.root.rglob('*')]}

    def test_repeat_commands_do_not_change_metadata_of_existing_task_files(self):
        own_workspace(self.root,self.uid);before=self.signatures()
        own_workspace(self.root,self.uid)
        self.assertEqual(self.signatures(),before)
        self.assertTrue(all(item[1:]==(self.uid,self.uid) for item in before.values()))

    def test_new_host_file_is_assigned_without_touching_existing_task_data(self):
        own_workspace(self.root,self.uid);old=(self.root/'nested/data').stat()
        reply=self.root/'reply';reply.write_bytes(b'ready')
        own_workspace(self.root,self.uid)
        self.assertEqual(reply.stat().st_uid,self.uid)
        self.assertEqual((self.root/'nested/data').stat().st_ctime_ns,old.st_ctime_ns)

    def test_hard_links_are_still_rejected_when_owned_by_task(self):
        own_workspace(self.root,self.uid)
        os.link(self.root/'nested/data',self.root/'linked')
        with self.assertRaisesRegex(ValueError,'Hard-linked'):own_workspace(self.root,self.uid)

    def test_symlink_target_outside_workspace_is_unchanged(self):
        with tempfile.TemporaryDirectory(prefix='pptx-owner-canary-') as directory:
            outside=Path(directory)/'private';outside.write_bytes(b'keep');before=outside.stat()
            (self.root/'link').symlink_to(outside)
            own_workspace(self.root,self.uid)
            self.assertEqual(outside.stat().st_uid,before.st_uid)
            self.assertEqual(outside.stat().st_ctime_ns,before.st_ctime_ns)
            self.assertTrue(stat.S_ISLNK((self.root/'link').lstat().st_mode))


if __name__=='__main__':unittest.main()
