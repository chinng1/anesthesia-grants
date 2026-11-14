#!/usr/bin/env python3
"""Embed grants.json into the HTML tool and write _site/index.html for GitHub Pages."""
import json
import re
from pathlib import Path

root = Path(__file__).parent
db = json.loads((root / 'grants.json').read_text())
html = (root / 'grants tool 2.0.html').read_text()
new_data = 'const db = ' + json.dumps(db, separators=(',', ':')) + ';'
html, count = re.subn(r'const db = \{.*?\};', lambda m: new_data, html, count=1, flags=re.DOTALL)
if count != 1:
    raise SystemExit('Could not find "const db = {...};" in the HTML')
out = root / '_site'
out.mkdir(exist_ok=True)
(out / 'index.html').write_text(html)
(out / '.nojekyll').write_text('')
print(f"Built _site/index.html with {len(db['grants'])} grants (v{db['_meta']['version']})")
