#creates wide dataframe of virginia data

import pandas as pd

df = pd.read_csv("data/places_county_clean.csv")

COUNTY = "locationid"
STATE = "statedesc"
DISEASE = "measure"
VALUE_AA = "adj_prevalence"
VALUE_RAW = "crude_prevalence"

df_aa = df.pivot_table(
    index=[COUNTY, STATE],
    columns=DISEASE,
    values=VALUE_AA,
).reset_index()

df_raw = df.pivot_table(
    index=[COUNTY, STATE],
    columns=DISEASE,
    values=VALUE_RAW,
).reset_index()

va_aa = df_aa[df_aa[STATE] == "Virginia"].copy()
va_raw = df_raw[df_raw[STATE] == "Virginia"].copy()

# locationid from CDC PLACES county data is a 5-digit county FIPS code —
# make sure it's a zero-padded string (not a stray float/int) so it lines
# up with any FIPS-keyed geojson.
va_raw[COUNTY] = va_raw[COUNTY].astype(str).str.zfill(5)
va_aa[COUNTY] = va_aa[COUNTY].astype(str).str.zfill(5)

# Disease list = every pivoted column except the two index columns
DISEASES = sorted(c for c in va_raw.columns if c not in (COUNTY, STATE))