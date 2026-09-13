"""Replay raw scoring/usage with the frozen audit, then archive without binaries."""
import sys
import run_comparison as run

sys.modules['run_guidance'] = run.guidance
frozen = run.module('scoped_frozen_archive', run.EVIDENCE / 'routing-2026-09-06/comparison/archive.py')


if __name__ == '__main__':
    frozen.main()
