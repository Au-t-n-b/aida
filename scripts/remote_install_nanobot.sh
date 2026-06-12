#!/bin/bash
set -e
cd /opt/aida_liwen/nanobot-main
rm -rf .venv
python3.11 -m venv .venv
.venv/bin/pip install -U pip -q
.venv/bin/pip install -e ".[api]"
echo NANOBOT_INSTALLED_OK
