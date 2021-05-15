#!/usr/bin/env python3

import platform
import sys

import pytest

ARGS = [#'--collect-only',
        #'--verbose',
        #'--pdb',
        #'--exitfirst',  # a.k.a. '-x'
        #'-W', 'error',
        ]

if platform.system() == 'Windows':
    ARGS.append('--pdb')

sys.exit(pytest.main(ARGS + sys.argv[1:]))
