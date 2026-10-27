"""Compatibility entrypoint; copy beside the existing private bridge settings."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
WORKER=ROOT.parent/'.work/interactive-runtime-20260920/repo/runner'
if not (WORKER/'runner.py').is_file():WORKER=ROOT
sys.path.insert(0,str(WORKER))
from production_bridge import run

if __name__=='__main__':run(WORKER,ROOT/'settings.local.json')
