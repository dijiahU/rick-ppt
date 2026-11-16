import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pptx-agent/skills/pptx/scripts'))
import native_batch  # noqa: E402


class TaskPathScopeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.root = base / 'task'
        (self.root / 'ws').mkdir(parents=True)
        (self.root / 'ws/a.txt').write_text('x')
        self.alias = base / 'alias'          # like macOS /tmp -> /private/tmp
        os.symlink(base, self.alias)

    def tearDown(self):
        self.tmp.cleanup()

    def test_symlinked_ancestor_of_root_is_accepted(self):
        got = native_batch._scoped(self.root, self.alias / 'task/ws/a.txt')
        self.assertEqual(got, self.root / 'ws/a.txt')
        got = native_batch._scoped(self.root, str(self.alias / 'task/ws'), directory=True)
        self.assertEqual(got, self.root / 'ws')

    def test_symlink_inside_task_is_still_rejected(self):
        os.symlink(self.root / 'ws', self.root / 'link')
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            native_batch._scoped(self.root, self.root / 'link/a.txt')

    def test_outside_path_is_still_rejected(self):
        outside = Path(self.tmp.name).resolve() / 'other.txt'
        outside.write_text('x')
        with self.assertRaisesRegex(ValueError, 'inside the task root'):
            native_batch._scoped(self.root, self.alias / 'other.txt')


if __name__ == '__main__':
    unittest.main()
