#!/usr/bin/python3

import collections
import datetime
import operator

import numpy as np
import pandas as pd
import requests
import scipy.optimize
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as pltdates
from matplotlib.offsetbox import AnchoredText

################################################################################
# tweakable parameters

# The plots
#
# title: plot title
# label: label (prefix) in legend
# color: plot color
# json: name of attribute in json data
# plot: no. of plot in axes(2, 2)
# offset: no. of days to shift the milestones

PLOTS = collections.OrderedDict (
    pos = {
        'title'  : 'Positive tests per day',
        'label'  : 'Positive tests',
        'color'  : '#0000ff',
        'json'   : 'Totalt_antal_fall',
        'plot'   : 3,
        'offset' : 7, # days from infection to positive test, mostly guessed
                      # Reporting delay estimated to be 7-8 days (See: Table 1):
                      # https://www.stablab.stat.uni-muenchen.de/_assets/docs/nowcasting_covid19_bavaria.pdf
    },
    icu = {
        'title'  : 'Intensive care hospitalizations per day',
        'label'  : 'Entered ICU',
        'color'  : '#ff0000',
        'json'   : 'Antal_intensivvardade',
        'plot'   : 1,
        'offset' : 11, # days from infection to icu admission,
                       # "Days from onset to ICU care: 11,1 (0 - 53,7) (min-max)"
                       # -- https://www.icuregswe.org/en/data--results/covid-19-in-swedish-intensive-care/
    },
    died = {
        'title'  : 'Deaths per day',
        'label'  : 'Died',
        'color'  : '#000000',
        'json'   : 'Antal_avlidna',
        'plot'   : 2,
        'offset' : 17, # days from infection to death, calculated: 11.5 + 5.1
                       # "symptom to death 11.5 days"
                       # -- https://www.worldometers.info/coronavirus/coronavirus-death-rate/
                       # also confirmed by curve overlay
    },
)

# Milestones to annotate
#
# https://en.wikipedia.org/wiki/COVID-19_pandemic_in_Sweden#Measures
# https://www.edarabia.com/school-holidays-sweden/

MILESTONES = (
    # ( pd.to_datetime ('2020-02-08'), 'winter school break in central sweden' ),
    # ( pd.to_datetime ('2020-02-17'), 'end of winter school break in central sweden' ),
    # ( pd.to_datetime ('2020-02-15'), 'winter school break in south sweden' ),
    # ( pd.to_datetime ('2020-02-24'), 'end of winter school break in south sweden' ),
    # ( pd.to_datetime ('2020-02-22'), 'winter school break in stockholm' ),
    # ( pd.to_datetime ('2020-03-02'), 'end of winter school break in stockholm' ),
    # ( pd.to_datetime ('2020-02-29'), 'winter school break in north sweden' ),
    # ( pd.to_datetime ('2020-03-09'), 'end of winter school break in north sweden' ),

    ( pd.to_datetime ('2020-03-04'), 'new test strategy' ),
    ( pd.to_datetime ('2020-03-11'), 'limited public gatherings to 500 persons' ),
    ( pd.to_datetime ('2020-03-13'), 'waivered sick certificates' ),
    ( pd.to_datetime ('2020-03-16'), 'recommended social distancing for 70+' ),
    ( pd.to_datetime ('2020-03-17'), 'recommended work from home and distance learning' ),
    ( pd.to_datetime ('2020-03-18'), 'recommended travelling avoidance' ),
    ( pd.to_datetime ('2020-03-24'), 'mandated distance for restaurant tables' ),
    ( pd.to_datetime ('2020-03-27'), 'limited public gatherings to 50 persons' ),
    ( pd.to_datetime ('2020-04-01'), 'closed nursing homes to visitors' ),

    ( pd.to_datetime ('2020-04-04'), 'start of easter school break in stockholm' ),
    ( pd.to_datetime ('2020-04-10'), 'start of easter school breaks in north and south sweden' ),
    ( pd.to_datetime ('2020-04-14'), 'end of easter school breaks' ),

    ( pd.to_datetime ('2020-04-18'), 'start of easter school break in central sweden' ),
    ( pd.to_datetime ('2020-04-23'), 'end of easter school break in central sweden' ),

    ( pd.to_datetime ('2020-05-01'), 'may first' ),
)

# Parameters used to estimate R
#
# https://www.folkhalsomyndigheten.se/contentassets/e1c3b83fa24f4d019e4842053ffd8300/estimates-peak-day-infected-during-covid-19-outbreak-stockholm-feb-apr-2020.pdf
# But see also: https://www.hindawi.com/journals/cmmm/2011/527610/

LATENCY_DAYS    = 5.1  # aka. incubation time
INFECTIOUS_DAYS = 5    # no. of days a person stays infectious
# mean time between infections in infection chain
# assuming infectiousness starts 1 day before symptom onset
# and most infections happen early in the infectious window
MEAN_GENERATION_INTERVAL = ((LATENCY_DAYS - 1) + (INFECTIOUS_DAYS / 4))
# assumed peak day of the pandemic
HUMP_DAY        = '2020-03-24' # fit curve starting here

# other parameters

START_DATE      = '2020-03-15' # start date for plots
UNSTABLE_DAYS   = 10           # ignore the last X days of data because it is unstable
ROLL_DAYS       = 7            # smooth data by rolling average over X days

# end tweakable parameters
################################################################################

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
pd.set_option ('mode.chained_assignment', 'raise')

attributes = [ feature['attributes'] for feature in r.json ()['features'] ]
getter = operator.itemgetter (*[ a['json'] for a in PLOTS.values ()])
data = [ getter (a) for a in attributes ]
index = [ pd.to_datetime (a['Statistikdatum'], unit = 'ms') for a in attributes ]

df = pd.DataFrame (
    data = data,
    index = index,
    columns = pd.MultiIndex.from_product ([PLOTS.keys (), ['raw']])
)

end_date = df.index[-1] - pd.Timedelta (UNSTABLE_DAYS, 'days')

for col in PLOTS:
    df[(col, 'roll')]     = df[(col, 'raw')].rolling (ROLL_DAYS, center = True).mean ()
    df[(col, 'stable')]   = df.loc[:end_date, (col, 'roll')]
    df[(col, 'unstable')] = df.loc[end_date:, (col, 'roll')]

def f (x, a, b):
    """ The exponential curve to fit. """
    return a * np.exp (b * x)

def fit_data (field, start_date):
    """ Fit the dataset to an exponential curve. """

    popt, pcov = scipy.optimize.curve_fit (
        f,
        (df[start_date:end_date].index - start_date).days,
        df.loc[start_date:end_date, (field, 'stable')],
        bounds = ([0., -5.], [1000., 5.])
    )
    df.loc[start_date:, (field, 'fit')] = f ((df[start_date:].index - start_date).days, *popt)

    return popt, pcov

def annotate_milestones (ax, offset):
    """ Draw the vertical lines corresponding to the milestones. """
    ymin, ymax = ax.get_ylim ()
    for date, caption in MILESTONES:
        ax.axvline (x = date + offset)
        ax.annotate (caption, xy = (date + offset, ymin),
                     xytext = (2, 12), textcoords = 'offset points',
                     rotation = 'vertical')

def set_xticks (ax):
    """ Format the time-axis ticks. """
    @matplotlib.ticker.FuncFormatter
    def minor_formatter (x, pos):
        d = pltdates.num2date (x)
        if d.weekday () == 0:
            return d.strftime ('%d')
        return ''

    ax.xaxis.set_minor_locator   (pltdates.DayLocator ())
    ax.xaxis.set_minor_formatter (minor_formatter)
    ax.xaxis.set_major_locator   (pltdates.MonthLocator ())
    ax.xaxis.set_major_formatter (pltdates.DateFormatter ('%B'))
    ax.xaxis.set_tick_params (which = 'major', pad = 20)

def plot (field, data):
    """ Plot one curve and annotate it. """

    ax = plt.subplot (2, 2, data['plot'])
    ax.set_title (data['title'], fontsize = 16)

    offset = pd.Timedelta (data['offset'], 'days')
    color  = data['color']
    start_date = pd.to_datetime (HUMP_DAY) + offset
    popt, pcov = fit_data (field, start_date)

    ax.bar (
        df.index,
        df[(field, 'raw')],
        color = color + '10',
        label = data['label'] + ' (raw)',
        width = 1.0
    )

    params = [
        ('stable',   'ff', '-',  data['label'] + ' (7 day rolling avg.)'),
        ('unstable', 'ff', ':',  ''),
        ('fit' ,     'ff', '--', 'Fit: %5.1f e^(%5.4f x)\nEstimated R: %5.3f' % (
            popt[0],
            popt[1],
            # See: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1766383/
            # Section: (c) Delta distributions
            np.exp (popt[1] * MEAN_GENERATION_INTERVAL)
        ))
    ]
    for level2, alpha, style, labell in params:
        ax.plot (
            df.index,
            df[(field, level2)],
            color = color + alpha,
            linestyle = style,
            label = labell
        )

    ymin_, ymax = ax.get_ylim ()
    ax.set_ylim (0, ymax)
    ax.set_xlim (pd.to_datetime (START_DATE), df.index[-1])
    ax.legend (loc = 'upper right')

    set_xticks (ax)
    annotate_milestones (ax, offset)

    note = AnchoredText ("""
Milestones are offset by %d days.
Data for the last %d days is incomplete.
Complete data from %s on is
used for least squares curve fitting.""".strip () % (offset.days, UNSTABLE_DAYS, start_date.strftime ('%Y-%m-%d')), loc = 'upper left')
    ax.add_artist (note)


##################
# start plotting #
##################

fig, axs = plt.subplots (2, 2)
fig.set_size_inches (24, 24)

fig.suptitle ('Covid-19 Pandemic in Sweden\n(Last updated on %s. Data source: Folkhälsomyndigheten)'
              % datetime.datetime.now ().strftime ('%Y-%m-%d %H:%M'),
              fontsize = 24)

# the three data plots

for k, v in PLOTS.items ():
    plot (k, v)

# the special plot: overlay of all three curves

ax = plt.subplot (2, 2, 4)
ax.set_title ('Curve Overlay', fontsize = 16)

for field, data in PLOTS.items ():
    # normalize curve maxima to 1 and offset curves
    col_max = df[(field, 'roll')].max ()
    for level2 in 'stable', 'unstable':
        col = (field, level2)
        df.loc[:, col] = df[col] / col_max
        df.loc[:, col] = df[col].shift (-data['offset'])
    ax.plot (
        df.index,
        df[(field, 'stable')],
        color = data['color'],
        linestyle = '-',
        label = data['label'] + ' (offset by %d days)' % -data['offset']
    )
    ax.plot (
        df.index,
        df[(field, 'unstable')],
        color = data['color'],
        linestyle = ':'
    )

ax.legend (loc = 'upper right')
ax.set_ylim (0, 1.2)
end_date = df.index[-1] - pd.Timedelta (PLOTS['pos']['offset'], 'days')
ax.set_xlim (pd.to_datetime ('2020-03-01'), end_date)
ax.set_yticks ([], minor = True)
ax.set_yticks ([], minor = False)

set_xticks (ax)
annotate_milestones (ax, pd.Timedelta (0, 'days'))

note = AnchoredText ("""
Curves are peak-normalized and offset
by the amount indicated in the legend.""".strip (), loc = 'upper left')
ax.add_artist (note)

# done
plt.savefig ('docs/sweden.png')
plt.show ()
