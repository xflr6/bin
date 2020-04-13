#!/usr/bin/env python3

import platform
import sys

import pytest

ARGS = [
    #'--exitfirst',
]

if platform.system() == 'Windows':
    ARGS.append('--pdb')

sys.exit(pytest.main(ARGS + sys.argv[1:]))
