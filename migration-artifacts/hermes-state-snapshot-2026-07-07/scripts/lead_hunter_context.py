#!/usr/bin/env python3
import subprocess
from pathlib import Path

PROFILE = Path.home() / '.hermes' / 'profiles' / 'lead-hunter-brussels'
TOOLS = PROFILE / 'tools'

for label, tool in [
    ('Lead ledger status', TOOLS / 'lead_ledger.py'),
    ('Airtable sync status', TOOLS / 'airtable_sync.py'),
]:
    cmd = ['python3', str(tool), 'status']
    try:
        output = subprocess.check_output(cmd, text=True)
        print(label + ':')
        print(output)
    except Exception as e:
        print(f'{label} unavailable: {e}')

print('Use the local ledger for dedupe before including new leads. Update the ledger after each run and sync Airtable when configured.')
