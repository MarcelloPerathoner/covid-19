#!/usr/bin/python3

import datetime

import numpy as np
import pandas as pd
import requests
import scipy.optimize
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnchoredText

# tweakable parameters

START_DATE    = '2020-03-16' # start date for plots
UNSTABLE_DAYS = 10           # ignore the last X days of data because it is unstable
HUMP_DAY      = '2020-03-24' # assumed tipping day of the pandemic
ROLL_DAYS     = 7            # smooth data by rolling average over X days

# Reporting delay estimated to be 7-8 days (See: Table 1):
# https://www.stablab.stat.uni-muenchen.de/_assets/docs/nowcasting_covid19_bavaria.pdf
#
# "Days from onset to ICU care: 11,1 (0 - 53,7) (min-max)"
# https://www.icuregswe.org/en/data--results/covid-19-in-swedish-intensive-care/
#
# https://www.worldometers.info/coronavirus/coronavirus-death-rate/
# symptom to death 11.5 days
#
# 7, 11, 17

OFFSETS = {
    'pos'  :  7, # days from infection to positive test, mostly guessed
    'icu'  : 11, # days from infection to icu admission, pretty well established by curve overlay
    'died' : 17, # days from infection to death, calculated: 11.5 + 5.1
}

MILESTONES = ( # milestone dates
    ( pd.to_datetime ('2020-03-11'), 0, 'limited public gatherings to 500 persons' ),
    ( pd.to_datetime ('2020-03-13'), 0, 'waivered sick certificates' ),
    ( pd.to_datetime ('2020-03-16'), 0, 'recommended social distancing for 70+' ),
    ( pd.to_datetime ('2020-03-17'), 0, 'recommended work from home and distance learning' ),
    ( pd.to_datetime ('2020-03-18'), 0, 'recommended travelling avoidance' ),
    ( pd.to_datetime ('2020-03-24'), 1, 'mandated distance for restaurant tables' ),
    ( pd.to_datetime ('2020-03-27'), 1, 'limited public gatherings to 50 persons' ),
    ( pd.to_datetime ('2020-04-01'), 1, 'closed nursing homes to visitors' ),
    ( pd.to_datetime ('2020-04-04'), 0, 'start of easter school break in stockholm' ),
    ( pd.to_datetime ('2020-04-14'), 0, 'end of easter school break in stockholm' ),
)

# The following parameters are used to estimate R
# https://www.folkhalsomyndigheten.se/contentassets/e1c3b83fa24f4d019e4842053ffd8300/estimates-peak-day-infected-during-covid-19-outbreak-stockholm-feb-apr-2020.pdf

LATENCY_DAYS    = 5.1
INFECTIOUS_DAYS = 5
# assuming infectiousness starts 1 day before symptom onset
# and most infections happen early in the infectious window
MEAN_GENERATION_INTERVAL = ((LATENCY_DAYS - 1) + (INFECTIOUS_DAYS / 4))

COLORS = {
    'pos'  : '#0000ff',
    'icu'  : '#ff0000',
    'died' : '#000000',
}

# end tweakable parameters

COLUMNS = ['pos', 'icu', 'died']

# get the data from Folkhälsomyndigheten into pandas
#
# Dashboard: https://experience.arcgis.com/experience/09f821667ce64bf7be6f9f87457ed9aa
# Available tables see:
# https://services5.arcgis.com/fsYDFeRKu1hELJJs/ArcGIS/rest/services/FOHM_Covid_19_FME_1/FeatureServer/layers

r = requests.get (
    "https://services5.arcgis.com/fsYDFeRKu1hELJJs/arcgis/rest/services/FOHM_Covid_19_FME_1/FeatureServer/1/query",
    params = {
        'f'                 : 'json',
        'where'             : '1=1',
        'returnGeometry'    : 'false',
        'spatialRel'        : 'esriSpatialRelIntersects',
        'outFields'         : 'Statistikdatum, Totalt_antal_fall, Antal_intensivvardade, Antal_avlidna',
        'orderByFields'     : 'Statistikdatum asc',
        'outSR'             : '102100',
        'resultOffset'      : 0,
        'resultRecordCount' : 32000,
        'resultType'        : 'standard',
        'cacheHint'         : 'true',
    }, headers = {
        "accept"            : "*/*",
        "accept-language"   : "de,en;q=0.9,en-US;q=0.8",
        "sec-fetch-dest"    : "empty",
        "sec-fetch-mode"    : "cors",
        "sec-fetch-site"    : "same-site",
        "referer"           : "https://fohm.maps.arcgis.com/apps/opsdashboard/index.html",
    })

r.raise_for_status ()

attributes = [ feature['attributes'] for feature in r.json ()['features'] ]
data = [ [ a['Totalt_antal_fall'], a['Antal_intensivvardade'], a['Antal_avlidna'] ] for a in attributes ]
index = [ pd.to_datetime (a['Statistikdatum'], unit = 'ms') for a in attributes ]

df = pd.DataFrame (data = data, index = index, columns = COLUMNS)
for col in COLUMNS:
    df[col + '_roll'] = df[col].rolling (ROLL_DAYS, center = True).mean ()

end_date = df.index[-1] - pd.Timedelta (UNSTABLE_DAYS, 'days')

# merge in milestones
df['mil'] = 0
ms = list (zip (*MILESTONES))
df.loc[ms[0], 'mil'] = ms[1]
df['mil'] = -df['mil']

def f (x, a, b):
    return a * np.exp (b * x)

def fit_data (field, start_date, end_date):
    """ fit the dataset to an exponential curve """

    dff = df [df.index  >= start_date]
    dff = dff[dff.index <= end_date]

    popt, pcov = scipy.optimize.curve_fit (f, (dff.index - start_date).days, dff[field],
                                           bounds = ([0., -5.], [1000., 5.]))
    df[field + '_fit'] = f ((df.index - start_date).days, *popt)
    df.loc[df.index < start_date, field + '_fit'] = np.nan

    return popt, pcov

def annotate_milestones (ax, offset):
    ymin, ymax = ax.get_ylim ()
    for m in MILESTONES:
        ax.axvline (x = m[0] + offset)
        ax.annotate (m[2], xy = (m[0] + offset, ymin),
                     xytext = (2, 12), textcoords = 'offset points',
                     rotation = 'vertical')

def plot ():
    """ plot one curve and annotate it """

    offset = pd.Timedelta (OFFSETS[field], 'days')
    color  = COLORS[field]
    start_date = pd.to_datetime (HUMP_DAY) + offset
    popt, pcov = fit_data (field, start_date, end_date)

    dff = df[df.index >= pd.to_datetime (START_DATE)] # cutoff early data

    dff.plot (ax = ax, kind = 'line',
              y     = [field, field + '_roll', field + '_fit'],
              color = map (lambda x: color + x, ['60', 'ff', 'ff']),
              style = [':', '-', '--'],
              label = [label,
                       label + ' (7 day rolling avg.)',
                       'Fit: %5.1f e^(%5.4f x)\nEstimated R: %5.3f' % (
                           popt[0],
                           popt[1],
                           # See: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1766383/
                           # Section: (c) Delta distributions
                           np.exp (popt[1] * MEAN_GENERATION_INTERVAL)
                       )
              ])

    ymin_, ymax = ax.get_ylim ()
    ax.set_ylim (0, ymax)

    annotate_milestones (ax, offset)

    note = AnchoredText ("""
Milestones are offset by %d days.
Data for the last %d days is incomplete.
Data in the shaded area is used
for least squares curve fitting.""".strip () % (offset.days, UNSTABLE_DAYS), loc = 'upper left')
    ax.add_artist (note)

    ax.axvspan (start_date, end_date, alpha = 0.1, color=color + '80')
    ax.set_title (title, fontsize = 16)


##################
# start plotting #
##################

fig, axs = plt.subplots (2, 2)
fig.set_size_inches (24, 24)

fig.suptitle ('Covid-19 Pandemic in Sweden\n(Last updated on %s. Data source: Folkhälsomyndigheten)'
              % datetime.datetime.now ().strftime ('%Y-%m-%d %H:%M'),
              fontsize = 24)

# plot tests

title  = 'Positive tests per day'
label  = 'Positive tests'
field  = 'pos'

ax = plt.subplot (2, 2, 3)
plot ()

# plot icu

title  = 'Intensive care hospitalizations per day'
label  = 'Entered ICU'
field  = 'icu'

ax = plt.subplot (2, 2, 1)
plot ()

# plot died

title  = 'Deaths per day'
label  = 'Died'
field  = 'died'

ax = plt.subplot (2, 2, 2)
plot ()

# plot overlay of all three curves

# normalize curves to 0..1 and offset them
for column in COLUMNS:
    col = column + '_roll'
    df[col] = df[col] / df[col].max ()
    df[col] = df[col].shift (-OFFSETS[column])

ax = plt.subplot (2, 2, 4)
ax.set_title ('Curve Overlay', fontsize = 16)
dff = df[df.index >= pd.to_datetime ('2020-03-01')] # cutoff early data
end_date = dff.index[-1] - pd.Timedelta (OFFSETS['pos'], 'days')
dff = dff[dff.index <= end_date] # cutoff late data

dff.plot (ax = ax, kind = 'line',
          y     = list (map (lambda x: x + '_roll', COLUMNS)),
          color = list (map (lambda x: COLORS[x],   COLUMNS)),
          style = '-',
          label = ['Positive tests (offset by %d days)' % -OFFSETS['pos'],
                   'Entered ICU (offset by %d days)'    % -OFFSETS['icu'],
                   'Died (offset by %d days)'           % -OFFSETS['died']])

ymin_, ymax = ax.get_ylim ()
ax.set_ylim (0, ymax)
annotate_milestones (ax, pd.Timedelta (0, 'days'))

# done
plt.savefig ('docs/sweden.png')
# plt.show ()
