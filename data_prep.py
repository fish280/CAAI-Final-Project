#creates wide dataframe of virginia data
#also splits into more specific types of measures ()

import pandas as pd

df = pd.read_csv("data/places_county_clean.csv")

#name variables
FIPS = "locationid"
COUNTY = "locationname"
STATE = "statedesc"
MEASURE = "measure"
VALUE_AA = "adj_prevalence"
VALUE_RAW = "crude_prevalence"
POPULATION = "totalpopulation"

df[FIPS] = df[FIPS].astype(str).str.zfill(5)

#change data shape, age-adjusted
df_aa = df.pivot_table(
    index=[FIPS, COUNTY, STATE, POPULATION],
    columns=MEASURE,
    values=VALUE_AA,
).reset_index()

#change data shape, crude
df_raw = df.pivot_table(
    index=[FIPS, COUNTY, STATE, POPULATION],
    columns=MEASURE,
    values=VALUE_RAW,
).reset_index()

DISEASES = ["All teeth lost among adults aged >=65 years", 
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









#print(va_aa[va_aa["population"].isna()][COUNTY])
