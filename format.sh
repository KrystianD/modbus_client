#!/bin/bash
cd $(dirname "$0")
autopep8 --recursive --in-place --max-line-length 120 -a .