"""ISHWORKZERO release gate: deterministic local verification entry point."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def run(*args):
    print('+', ' '.join(args), flush=True)
    return subprocess.run(args,cwd=ROOT,check=False).returncode
def main():
    checks=[(sys.executable,'-m','compileall','-q','ishworkzero'),(sys.executable,'-m','pytest','-q')]
    for cmd in checks:
        if run(*cmd)!=0:
            print('RELEASE_GATE=FAIL'); return 1
    print('RELEASE_GATE=GREEN'); return 0
if __name__=='__main__': raise SystemExit(main())
