.. -*- encoding: utf-8; fill-column: 72 -*-

Covid-19 Pandemic in Sweden
===========================

A data analysis with Python pandas.

This analysis has only two main parameters:

- the mean number of days between infection and ICU admission: 11 days [ICUREG2020]_,

- the mean number of days between infection and death: 17 days [WORLDO2020]_.

These two parameters are also confirmed by the overlay of two curves.

Data source: Folkhälsomyndigheten [#1]_.
Milestones: Wikipedia [#2]_.
Holidays: Edarabia [#3]_.


Results
-------

It emerges from this analysis that
while many factors may have contributed to the decline in Covid-related deaths in Sweden
the single smartest move was distancing in restaurants.

Covid spreads fastest by talking in closed spaces.
The super-spreading events in Germany: one carnival session, one beer fest, one church choir,
one ski bar, also confirm this fact.

It also emerges that the dumbest move is closing schools.
Children have more contact with their grandparents when schools are closed.
The mobility gained by the general population while schools are closed
more than outweighs the reduced spread between children.
Fortunately Sweden never blundered on that one,
but you can clearly see from the plots that during school vacations
Covid spreads much faster than at other times.

R is calculated in the most simple way and is informal only.
There are way too many different ways to calculate R to make R a meaningful number. [JING2011]_

.. image: https://raw.githubusercontent.com/MarcelloPerathoner/covid-19/master/docs/sweden.png
   :width: 100%
   :align: center

Big image: https://raw.githubusercontent.com/MarcelloPerathoner/covid-19/master/docs/sweden.png


.. rubric:: Footnotes

.. [#1] Folkhälsomyndigheten Covid dashboard.
        https://experience.arcgis.com/experience/09f821667ce64bf7be6f9f87457ed9aa

.. [ICUREG2020] https://www.icuregswe.org/en/data--results/covid-19-in-swedish-intensive-care/

.. [WORLDO2020] https://www.worldometers.info/coronavirus/coronavirus-death-rate/

.. [#2] https://en.wikipedia.org/wiki/COVID-19_pandemic_in_Sweden#Measures

.. [#3] https://www.edarabia.com/school-holidays-sweden/

.. [JING2011] Jing Li, Daniel Blakeley, and Robert J. Smith?.
             The Failure of R0.
             2011.  Computational and Mathematical Methods in Medicine.
             https://www.hindawi.com/journals/cmmm/2011/527610/
