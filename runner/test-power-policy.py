"""Synthetic AC/battery transitions: no real power changes, signals or jobs."""
import importlib.util
import os
from pathlib import Path
import subprocess
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import power_policy as power
from resilience import LeaseKeeper, PowerInterrupted, TaskPaused


class PowerTests(unittest.TestCase):
    def test_power_source_uses_supply_not_charge_percentage(self):
        for text, expected in [
            ("Now drawing from 'AC Power'\n100%; charged", 'ac'),
            ("Now drawing from 'Battery Power'\n100%; discharging", 'battery'),
            ('unrecognized', 'unknown'), ('', 'unknown')]:
            with self.subTest(expected=expected):
                self.assertEqual(power.power_source(lambda *a, **k: SimpleNamespace(returncode=0, stdout=text)), expected)
        self.assertEqual(power.power_source(lambda *a, **k: SimpleNamespace(returncode=1, stdout="'AC Power'")), 'unknown')

    def test_battery_or_unknown_blocks_opted_in_launcher(self):
        for source in ('battery', 'unknown', 'ac'):
            with patch.dict(os.environ, {'PPTX_WORKER_AC_ONLY': '1'}), patch.object(power, 'power_source', return_value=source):
                self.assertEqual(power.may_start(), source == 'ac')
        with patch.dict(os.environ, {}, clear=True), patch.object(power, 'power_source') as probe:
            self.assertTrue(power.may_start()); probe.assert_not_called()

    def test_launcher_returns_before_reading_credentials_or_spawning(self):
        spec=importlib.util.spec_from_file_location('start_worker', Path(__file__).with_name('start-worker.py'))
        launcher=importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)
        with patch.object(power, 'may_start', return_value=False), patch('sys.argv', ['start-worker.py']), patch.object(launcher, 'launch_environment') as env, patch.object(launcher.subprocess, 'Popen') as spawn:
            launcher.main(); env.assert_not_called(); spawn.assert_not_called()

    def test_unplug_latches_interrupt_and_stops_even_after_replug(self):
        stop=threading.Event(); interrupt=threading.Event()
        values=iter(['ac', 'battery', 'ac'])
        thread=power.watch(stop, interrupt, source=lambda:next(values), interval=.001)
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive()); self.assertTrue(stop.is_set()); self.assertTrue(interrupt.is_set())
        # Existing lease checkpoints interrupt the author/render path. This is
        # not an owner pause: the recoverable failure endpoint must still run.
        lease=LeaseKeeper(lambda:{'ok':True}, interrupt=interrupt)
        with self.assertRaises(PowerInterrupted): lease.check()
        self.assertFalse(issubclass(PowerInterrupted, TaskPaused))

    def test_owner_pause_still_takes_precedence(self):
        interrupt=threading.Event();interrupt.set()
        lease=LeaseKeeper(lambda:{'ok':True, 'stop':True}, interrupt=interrupt)
        lease.pulse()
        with self.assertRaises(TaskPaused):lease.check()


if __name__=='__main__': unittest.main()
