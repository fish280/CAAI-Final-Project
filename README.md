# County Health Atlas

An interactive Dash dashboard that maps chronic disease prevalence\
across U.S. counties and connects it to the risk factors, access\
gaps, and social determinants that help explain it.

---

# Project Overview

## The problem

Public health data is usually published as dense spreadsheets or\
single-topic reports, a national obesity rate here, a county\
diabetes table there. It's hard to see the full picture of what's\
happening in a given place, and harder still to connect a disease\
rate to \*why\* it's elevated in that specific county. National\
averages also hide enormous variation: a single U.S. figure can mask\
counties that are two or three times worse off than their\
neighbors.

## The audience

\- County and state health departments, deciding where to direct\
limited outreach and funding.\
- Healthcare providers and community organizations, looking to\
understand the access and social barriers their patient\
populations face.\
- Researchers and policy advocates, studying regional health\
disparities and what drives them.

## The value

Instead of reading a table of statistics, a user can see at a\
glance which counties carry the highest disease burden, what\
factors correlate with that burden, and who needs help first. The\
dashboard turns a static dataset into something explorable: filter\
by state, compare two counties directly, or rank every county in\
the country by a single measure.

The dashboard has four linked pages:

| Page | Question it answers |
|------------------------------------|------------------------------------|
| Health Overview | Where is a given condition most common? |
| Drivers & Risk Factors | Is the outcome explained by its risk factors, or is something else going on? |
| Access & Social Determinants | Which counties have the biggest gaps in healthcare access and social needs? |
| At-Risk Counties | Which counties need help first, and why? |

---

## How to Run

### Local setup

1\. Clone the repo and cd from https://github.com/fish280/CAAI-Final-Project

2\. Create and activate an environment (conda or venv both work):\
\`\`\`bash\
conda create -n county-health-atlas python=3.12\
conda activate county-health-atlas\
\`\`\`

3\. Install dependencies (pinned versions live in\
\`requirements.txt\` so your local environment matches what's\
deployed):\
\`\`\`bash\
pip install -r requirements.txt\
\`\`\`

4\. Confirm the data file is in place. The app expects the CDC\
PLACES CSV at: data/places_county_clean.csv and, for the Health Overview map, the county boundary file at: data/geojson-counties-fips.json

Both are read from disk at startup by the \`\*\_prep.py\` modules —\
if either is missing, the app will fail to import with a\
\`FileNotFoundError\` before it even starts.

5\. Run the app:\
\`\`\`bash\
python app.py\
\`\`\`\
This starts Dash's built-in development server (with\
\`debug=True\`) at \`http://127.0.0.1:8050\`.

Deploying (Render)

The app is set up to deploy on \[Render\](https://render.com) as a\
web service:

\- Start command: gunicorn app:server\
\*\*

\`app.py\` exposes \`server = app.server\` (the underlying Flask app)\
specifically so Gunicorn has something to point at — Dash's own\
dev server isn't used in production.\
- \*\*Build command:\*\* \`pip install -r requirements.txt\`\
- Make sure \`data/places_county_clean.csv\` and\
\`data/geojson-counties-fips.json\` are committed to the repo (or\
otherwise available at build time) — the prep modules load them\
at import time, before any request is handled, so a missing file\
breaks the whole deploy rather than just one page.\
- No environment variables or API keys are required — the app reads\
only from local files.

---

## Data Sources

Primary source: CDC PLACES: County Data (GIS-Friendly Format),\
2025 release (https://data.cdc.gov/500-Cities-Places/PLACES-County-Data-GIS-Friendly-Format-2025-releas/i46a-9kgh/about_data),\
published by the CDC.

\- Coverage: \~3,144 U.S. counties and county-equivalents, \~2,950\
with fully complete data.\
- Format: CSV, long format (one row per county × health\
measure).\
- License: CDC data does not require a license for general use.\
- Methodology note: PLACES measures are \*modeled estimates\*, not\
direct counts — CDC combines Behavioral Risk Factor Surveillance\
System (BRFSS) survey data with local demographic data via\
small-area estimation to produce a rate for every county,\
including ones too small to survey directly at full statistical\
confidence. Smaller counties carry more estimation uncertainty\
than larger ones.\
- Survey year: The 2025 release is built mostly on 2023 BRFSS\
data, but five measures (all teeth lost, dental visits,\
mammograms, colorectal cancer screening, short sleep duration) are\
only collected every other year and so use 2022 data instead —\
\`year\` is not a single constant across the file.

Secondary source: Plotly's county-level GeoJSON\
boundaries (https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json)\
(FIPS-keyed), used to draw the county shapes on the Health Overview\
choropleth map. Committed to the repo rather than fetched at\
runtime, so a slow or failed network request can't take the app\
down on startup.

---

## Data Dictionary

Raw CSV: \`data/places_county_clean.csv\`

One row per county × health measure (long format). 114,609 rows,\
16 columns.

| Column | Type | Description |
|------------------------|------------------|------------------------|
| \`locationid\` | string (5-digit) | County FIPS code. Read and stored as a zero-padded string everywhere in the app — casting to int silently drops leading zeros (e.g. Alabama counties) and breaks every geographic join. |
| \`measure\` | string | Full CDC sentence describing the measure (e.g. "Diagnosed diabetes among adults"). Used for tooltips/footnotes where the exact denominator matters. |
| \`measureid\` | string | Short CDC code for the measure (e.g. \`DIABETES\`, \`ACCESS2\`). Used as the pivoted column name and as dictionary keys throughout the \`\*\_prep.py\` modules. |
| \`short_question_text\` | string | Plain-English display label (e.g. "Diabetes"). What's actually shown in dropdowns across the app. |
| \`category\` / \`categoryid\` | string | CDC's own grouping for the measure (Health Outcomes, Health Risk Behaviors, Prevention, etc.). |
| \`year\` | integer | BRFSS survey year backing this specific measure. Varies by measure — see the methodology note above. |
| \`crude_prevalence\` | float | Raw, unadjusted percentage of adults with the condition/behavior. |
| \`adj_prevalence\` | float | Age-adjusted percentage — re-weighted to a standard age distribution so a county isn't penalized purely for having an older population. |
| \`locationname\` | string | County name. |
| \`stateabbr\` / \`statedesc\` | string | State postal abbreviation and full name. |
| \`totalpopulation\` | integer | Total county population, all ages. |
| \`totalpop18plus\` | integer | County population aged 18+ (most PLACES measures are adult-only). |
| \`latitude\` / \`longitude\` | float | County centroid coordinates. |

### Measures used in the dashboard

Not every PLACES measure is used — each page selects a focused\
subset so the story stays legible rather than overwhelming:

Disease outcomes (Health Overview, Drivers & Risk Factors, At-Risk\
Counties): all teeth lost, arthritis, cancer (non-skin/melanoma),\
COPD, coronary heart disease, current asthma, depression, diagnosed\
diabetes, fair/poor self-rated health, frequent mental distress,\
frequent physical distress, high blood pressure, high cholesterol,\
obesity, stroke.

Risk factors & behaviors (Drivers & Risk Factors, At-Risk\
Counties): binge drinking, cholesterol screening, cognitive\
disability, colorectal cancer screening, current smoking, lack of\
health insurance, food insecurity, hearing disability, housing\
insecurity, independent living disability, lack of reliable\
transportation, lack of social/emotional support, loneliness,\
mammography use, mobility disability, no leisure-time physical\
activity, received food stamps, self-care disability, short sleep\
duration.

Access & Social Determinants (Page 3): reduced further to six\
measures for chart legibility:

| Code | Label | Cluster |
|------------------------|------------------------|------------------------|
| \`ACCESS2\` | Lacks health insurance | Access to Care |
| \`CHECKUP\` | No annual checkup \*(flipped from CDC's "% who got a checkup" so every bar reads the same direction: taller = worse)\* | Access to Care |
| \`FOODINSECU\` | Food insecurity | Social & Economic Strain |
| \`HOUSINSECU\` | Housing insecurity | Social & Economic Strain |
| \`LACKTRPT\` | Transportation barriers | Social & Economic Strain |
| \`EMOTIONSPT\` | Lack of social/emotional support | Social & Economic Strain |

### Two ways of reading the same rate

Every measure carries both a crude and an age-adjusted\
value. Crude is the raw observed rate; age-adjusted re-weights it as\
if every county had the same age distribution. A county where crude\
is much higher than adjusted is being driven by an older population,\
not necessarily worse health outcomes or access. A county where\
adjusted is much higher than crude has a genuinely elevated rate\
despite not skewing old — the more actionable finding for targeting\
resources. The dashboard defaults to age-adjusted figures for this\
reason, with a crude/raw toggle available where relevant.

---

## Known Data Limitations

\- 33 rows are fully suppressed (both \`crude_prevalence\` and\
\`adj_prevalence\` are \`NaN\`); CDC withholds estimates for\
populations under 50 (e.g. Loving County, TX). These are dropped\
wherever a chart or correlation requires both axes to have data.\
- Kentucky and Pennsylvania\*\* report no 2023 measures in this\
release, so they render unshaded on any 2023-based measure.\
- 11 states did not administer the BRFSS social-needs survey\
module\*\* in this cycle (Colorado, Florida, Kentucky, Oregon,\
Pennsylvania, South Dakota, Tennessee, Texas, Vermont, Washington,\
Wyoming), the Social & Economic Strain cluster on Page 3 has no\
data for these states.\
- All figures are county-level estimates, not individual\
measurements, a county with a high rate is not evidence about\
any specific resident, and a correlation between two county-level\
measures does not mean the same individuals are driving both.