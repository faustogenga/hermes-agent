#!/usr/bin/env python3
import subprocess
from pathlib import Path

PROFILE = Path.home() / '.hermes' / 'profiles' / 'lead-hunter-brussels'
TOOLS = PROFILE / 'tools'

commands = [
    ('Lead ledger status', ['python3', str(TOOLS / 'lead_ledger.py'), 'status']),
    ('Airtable enrichment status', ['python3', str(TOOLS / 'lead_enrichment_airtable.py'), 'status']),
    ('Dropbox app-folder status', ['python3', str(TOOLS / 'dropbox_app_folder.py'), 'status']),
    ('Next Airtable lead for enrichment', ['python3', str(TOOLS / 'lead_enrichment_airtable.py'), 'pick-next', '--limit', '1']),
]

for label, cmd in commands:
    try:
        output = subprocess.check_output(cmd, text=True)
        print(label + ':')
        print(output)
    except Exception as exc:
        print(f'{label} unavailable: {exc}')

print('Use Airtable as the control tower and Dropbox App Folder as the final dossier archive. If Dropbox auth is missing, report the blocker clearly and do not claim the dossier was archived.')
