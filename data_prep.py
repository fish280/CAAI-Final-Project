#creates wide dataframe of virginia data
#also splits into more specific types of measures ()

import pandas as pd

df = pd.read_csv("data/places_county_clean.csv")

#name variables
FIPS = "locationid"
COUNTY = "locationname"
STATE = "statedesc"
DISEASE = "measure"
VALUE_AA = "adj_prevalence"
VALUE_RAW = "crude_prevalence"

#change data shape, age-adjusted
df_aa = df.pivot_table(
    index=[FIPS, COUNTY, STATE],
    columns=DISEASE,
    values=VALUE_AA,
).reset_index()

#change data shape, crude
df_raw = df.pivot_table(
    index=[FIPS, COUNTY, STATE],
    columns=DISEASE,
    values=VALUE_RAW,
).reset_index()

#limit to just va
va_aa = df_aa[df_aa[STATE] == "Virginia"].copy()
va_raw = df_raw[df_raw[STATE] == "Virginia"].copy()

diseases = ["All teeth lost among adults aged >=65 years", 
                     "Arthritis among adults", 
                     "Cancer (non-skin) or melanoma among adults", 
                     "Chronic obstructive pulmonary disease among adults", 
                     "Coronary heart disease among adults", 
                     "Current asthma among adults", 
                     "Depression among adults",
                     "Diagnosed diabetes among adults", 
                     "Fair or poor self-rated health status among adults", 
                     "Frequent mental distress among adults", 
                     "Frequent physical distress among adults", 
                     "High blood pressure among adults", 
                     "High cholesterol among adults who have ever been screened", 
                     "Obesity among adults", 
                     "Stroke among adults"]

risk_factors = ["Binge drinking among adults",
                                             "Cholesterol screening among adults", 
                                             "Cognitive disability among adults", 
                                             "Colorectal cancer screening among adults aged 45–75 years", 
                                             "Current cigarette smoking among adults",
                                             "Current lack of health insurance among adults aged 18-64 years", 
                                             "Food insecurity in the past 12 months among adults", 
                                             "Hearing disability among adults", 
                                             "Housing insecurity in the past 12 months among adults", 
                                             "Independent living disability among adults", 
                                             "Lack of reliable transportation in the past 12 months among adults", 
                                             "Lack of social and emotional support among adults", 
                                             "Loneliness among adults",
                                             "Mammography use among women aged 50-74 years", 
                                             "Mobility disability among adults", 
                                             "No leisure-time physical activity among adults", 
                                             "Received food stamps in the past 12 months among adults", 
                                             "Self-care disability among adults", 
                                             "Short sleep duration among adults"]

#just virginia, health measures
va_aa_health = va_aa[[FIPS, COUNTY, STATE] + diseases].copy()
#just virginia, includes health risk factors (incl disability and prevention measures), social risk factors
va_aa_risk_and_social = va_aa[[FIPS, COUNTY, STATE] + risk_factors].copy()

va_raw_health = va_raw[[FIPS, COUNTY, STATE] + diseases].copy()
va_raw_risk_and_social = va_raw[[FIPS, COUNTY, STATE] + risk_factors].copy()











# locationid from CDC PLACES county data is a 5-digit county FIPS code —
# make sure it's a zero-padded string (not a stray float/int) so it lines
# up with any FIPS-keyed geojson.
va_raw[COUNTY] = va_raw[COUNTY].astype(str).str.zfill(5)
va_aa[COUNTY] = va_aa[COUNTY].astype(str).str.zfill(5)

# Disease list = every pivoted column except the two index columns
DISEASES = sorted(c for c in va_raw.columns if c not in (COUNTY, STATE))

