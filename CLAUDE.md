# CLAUDE.md — Anesthesia Grants Tool

## What This Is

A standalone single-file HTML grant-finder tool for anesthesia trainees and early faculty. No server required — open `grants.html` directly in any browser. Can be emailed to collaborators as a single file; no JSON file or internet connection needed to use it. Built for UCSF Anesthesia & Perioperative Care but broadly useful for any physician-scientist.

## Files

| File | Purpose |
|---|---|
| `grants.json` | Source-of-truth database (170 grants, 28 categories, v2.2.0) |
| `grants tool 2.0.html` | Standalone tool with JSON embedded inline; current working file |

## HTML Layout

- **Primary navigation:** Training-level tabs (All / Resident / Fellow+Post-doc / Early Career / Mid Career) with live grant counts
- **Secondary filters (sticky bar):** Keyword search, Research Focus (category), LOI Required, Citizenship
- **Content:** Two-tier category layout within each tab:
  - **Core categories** (14) shown expanded: Anesthesia, NIH, General/Broad, Medical Education Research, Diversity & Inclusion, Institutional (UCSF), Technology & AI, Government/NSF, Physician Wellness, Health Services & Disparities, Environmental Health, Pharma IIR, Device IIR, Pulmonary & Critical Care
  - **Disease & Specialty Topics** accordion (14 categories) collapsed by default; auto-expands when a disease category is selected via the focus filter
- **Cards show:** title, org, amount, stage tags, eligibility, deadline badge, LOI badge, link

## Database Schema (grants.json)

Each grant object:
```json
{
  "id": "kebab-case unique ID",
  "title": "Full grant name",
  "org": "Sponsoring organization",
  "org_abbrev": "Short name",
  "category": "One of 28 categories",
  "amount_min": 50000,
  "amount_max": 75000,
  "amount_label": "$50,000–$75,000",
  "duration": "1–2 years",
  "stages": ["fellow", "early-faculty"],
  "stage_notes": "Free-text eligibility nuance",
  "topics": ["anesthesia", "pain"],
  "topic_tags": ["Display Tag 1", "Display Tag 2"],
  "eligibility": "Plain-language summary",
  "deadline": "Human-readable deadline",
  "deadline_type": "ok | soon | unknown",
  "loi_required": "yes | no | check",
  "url": "https://...",
  "citizenship": "us-only | open | check",
  "specialty_restricted": false
}
```

Valid stage slugs: `resident`, `fellow`, `postdoc`, `early-faculty`, `mid-career`, `graduate`

## Current Categories (28)

Anesthesia, NIH, Cardiovascular, Cancer, Neuroscience & Aging, Pediatrics, General / Broad, Diabetes, Autoimmune & Rheumatology, Multiple Sclerosis, Autism, Hematology, Surgery, Medical Education Research, Government / NSF, Technology & AI, Pharma — Investigator-Initiated, Device — Investigator-Initiated, Pulmonary & Critical Care, Institutional (UCSF), Obstetrics & Women's Health, Sleep Medicine, Palliative Care, Diversity & Inclusion, Trauma, Environmental Health & Sustainability, Physician Wellness & Mental Health, Health Services & Disparities

## Re-embedding JSON into HTML

Run this after any changes to `grants.json`:

```bash
python3 << 'EOF'
import json, re
db = json.load(open('grants.json'))
html = open('grants tool 2.0.html').read()
new_data = 'const db = ' + json.dumps(db, separators=(',',':')) + ';'
html2 = re.sub(r'const db = \{.*?\};', lambda m: new_data, html, flags=re.DOTALL)
open('grants tool 2.0.html','w').write(html2)
print('Done,', len(db['grants']), 'grants embedded')
EOF
```

**Critical:** Use `lambda m: new_data` in `re.sub` — the JSON contains `\u` Unicode escapes that Python's re module misinterprets as regex backreferences if passed as a plain string replacement.

## Validation

```bash
python3 -c "
import json
db = json.load(open('grants.json'))
ids = [g['id'] for g in db['grants']]
dupes = [x for x in ids if ids.count(x) > 1]
print('Grants:', len(db['grants']), '| Dupes:', dupes or 'none')
from collections import Counter
for cat, n in Counter(g['category'] for g in db['grants']).most_common():
    print(f'  {cat}: {n}')
"
```

## HTML Stage Filter Map

```javascript
const STAGE_FILTER_MAP = {
  "resident":       s => s === "resident",
  "fellow-postdoc": s => s === "fellow" || s === "postdoc",
  "early-career":   s => s === "early-faculty",
  "mid-career":     s => s === "mid-career",
};
```

Category filter and topic filter are auto-populated from JSON at runtime.

## Coverage Notes

- **Anesthesia subspecialties:** trauma (EAST, AAST), OB/obstetric anesthesia (SOAP/FAER, SMFM), preeclampsia, malignant hyperthermia, cardiac/congenital, global health/surgery, regional anesthesia, pain medicine (ASRA ×3, IASP ×2, Rita Allen/USASP), sleep medicine, critical care (SCCM ×2, SOCCA, ESICM), sepsis, delirium/POCD (NIDUS, ADS), palliative care, neuroanesthesia (SNACC, NCS)
- **Diversity & equity:** RWJF Harold Amos, AAMC Nickens, Ford Foundation, NMA, NHMA, NIH MOSAIC K99/R00, NIH Diversity Supplement, NIH ORWH/BIRCWH K12
- **New categories (v1.7+):** Environmental Health & Sustainability (NIEHS, HEI, Wellcome, EPA STAR), Physician Wellness & Mental Health (AFSP, ACGME Back to Bedside, NIMH, AMA Foundation), Health Services & Disparities (AHRQ ×2, NIMHD ×2, Greenwall Bioethics, Commonwealth Fund Harkness, SGIM, AHA)
- **Deadlines:** flag `deadline_type: "soon"` for anything <6 weeks out; `"unknown"` if unverifiable
- **URL audit (v1.9.0):** All 167 URLs verified via live fetch. Removed 9 defunct/wrong entries; corrected 18 URLs. Do not restore removed grants without re-verifying the program is active.
- **v2.1.0 additions (2026-05-26):** ABA/FAER REG (not active this cycle), FAER Transition to Independence Grant (post-MRTG), PhRMA Foundation Faculty Starter Grants ($100K/1yr), Doris Duke CSDA (~$450K/3yr; no open cycle currently), Parker B. Francis Fellowship ($225K/3yr, pulmonary/critical care/sleep).
- **v2.2.0 changes (2026-05-26):** Renamed "Graduate Medical Education" → "Medical Education Research". Added ABMS REF Grant ($75K/2yr), SAEM Foundation ERTG ($100K/2yr, EM), AAMC GEA National Grant (up to $10K/2yr).

## Known URL Caveats

- Several sites block automated fetches (403) but are valid — APSF, FAER/ASA, EAST, ATS, Wellcome. Treat 403 as "probably fine, verify manually."
- NIH program announcement numbers (PA/PAR) rotate annually — use the canonical NIGMS/NIH institute pages rather than specific PA file URLs.
- RWJF program pages sometimes 404 when grants close; fall back to `rwjf.org/en/grants/active-programs.html`.
- Doris Duke: use `dorisduke.org` (not `ddcf.org` — that domain has an expired SSL cert as of 2026-05-26).
