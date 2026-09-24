#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) Open Astro Technologies, USA.
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora

# This file is part of the "PyJHora" Python library
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Calculates Vimshottari (=120) Dasha-bhukthi-antara-sukshma-prana
"""
from collections import OrderedDict as Dict
from jhora import const, utils
from jhora.panchanga import drik

year_duration = (
    const.sidereal_year
)  # const.tropical_year #  # some say 360 days, others 365.25 or 365.2563 etc
vimsottari_adhipati = lambda nak, seed_star=3: const.vimsottari_adhipati_list[
    (nak - seed_star + 3) % (len(const.vimsottari_adhipati_list))
]
vimsottari_dict = const.vimsottari_dict
human_life_span_for_vimsottari_dhasa = const.human_life_span_for_vimsottari_dhasa
### --- Vimoshatari functions
def vimsottari_next_adhipati(lord, dir=1):
    """Returns next guy after `lord` in the adhipati_list"""
    current = const.vimsottari_adhipati_list.index(lord)
    next_index = (current + dir) % len(const.vimsottari_adhipati_list)
    return const.vimsottari_adhipati_list[next_index]


def vimsottari_dasha_start_date(
    jd,
    place,
    divisional_chart_factor=1,
    chart_method=1,
    star_position_from_moon=1,
    seed_star=3,
    dhasa_starting_planet=1,
):
    """Returns the start date of the mahadasa which occured on or before `jd`"""
    y, m, d, fh = utils.jd_to_gregorian(jd)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)
    one_star = 360 / 27.0  # 27 nakshatras span 360°
    from jhora.horoscope.chart import charts, sphuta

    _special_planets = ["M", "G", "T", "I", "B", "I", "P"]
    planet_positions = charts.divisional_chart(
        jd,
        place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
    )
    if dhasa_starting_planet in [*range(9)]:
        planet_long = (
            planet_positions[dhasa_starting_planet + 1][1][0] * 30
            + planet_positions[dhasa_starting_planet + 1][1][1]
        )
    elif dhasa_starting_planet == const._ascendant_symbol:
        planet_long = planet_positions[0][1][0] * 30 + planet_positions[0][1][1]
    elif dhasa_starting_planet.upper() == "M":
        mn = drik.maandi_longitude(
            dob, tob, place, divisional_chart_factor=divisional_chart_factor
        )
        planet_long = mn[0] * 30 + mn[1]
    elif dhasa_starting_planet.upper() == "G":
        gl = drik.gulika_longitude(
            dob, tob, place, divisional_chart_factor=divisional_chart_factor
        )
        planet_long = gl[0] * 30 + gl[1]
    elif dhasa_starting_planet.upper() == "B":
        gl = drik.bhrigu_bindhu_lagna(
            jd,
            place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
        )
        planet_long = gl[0] * 30 + gl[1]
    elif dhasa_starting_planet.upper() == "I":
        gl = drik.indu_lagna(
            jd,
            place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
        )
        planet_long = gl[0] * 30 + gl[1]
    elif dhasa_starting_planet.upper() == "P":
        gl = drik.pranapada_lagna(
            jd,
            place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
        )
        planet_long = gl[0] * 30 + gl[1]
    elif dhasa_starting_planet.upper() == "T":
        sp = sphuta.tri_sphuta(
            dob,
            tob,
            place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
        )
        planet_long = sp[0] * 30 + sp[1]
    else:
        planet_long = planet_positions[2][1][0] * 30 + planet_positions[2][1][1]
    if dhasa_starting_planet == 1:
        planet_long += (star_position_from_moon - 1) * one_star
    nak = int(planet_long / one_star)
    rem = planet_long - nak * one_star
    lord = vimsottari_adhipati(nak, seed_star)  # ruler of current nakshatra
    period = vimsottari_dict[lord]  # total years of nakshatra lord
    # print('seed_star,nak,lord,period',seed_star,nak,lord,period)
    period_elapsed = rem / one_star * period  # years
    period_elapsed *= year_duration  # days
    start_date = jd - period_elapsed  # so many days before current day
    return [lord, start_date]


def vimsottari_mahadasa(
    jd,
    place,
    divisional_chart_factor=1,
    chart_method=1,
    star_position_from_moon=1,
    seed_star=3,
    dhasa_starting_planet=1,
):
    """List all mahadashas and their start dates"""
    lord, start_date = vimsottari_dasha_start_date(
        jd,
        place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        seed_star=seed_star,
        dhasa_starting_planet=dhasa_starting_planet,
    )
    retval = Dict()
    for i in range(9):
        retval[lord] = start_date
        start_date += vimsottari_dict[lord] * year_duration
        lord = vimsottari_next_adhipati(lord)

    return retval


def _vimsottari_rasi_bhukthi(maha_lord, maha_lord_rasi, start_date):
    """Compute all bhuktis of given nakshatra-lord of Mahadasa using rasi bhukthi variation
    and its start date"""
    retval = Dict()
    bhukthi_duration = vimsottari_dict[maha_lord] / 12
    for bhukthi_rasi in [(maha_lord_rasi + h) % 12 for h in range(12)]:
        retval[bhukthi_rasi] = start_date
        start_date += bhukthi_duration * year_duration
    return retval


def _vimsottari_bhukti(maha_lord, start_date, antardhasa_option=1):
    """Compute all bhuktis of given nakshatra-lord of Mahadasa
    and its start date"""
    lord = maha_lord
    if antardhasa_option in [3, 4]:
        lord = vimsottari_next_adhipati(lord, dir=1)
    elif antardhasa_option in [5, 6]:
        lord = vimsottari_next_adhipati(lord, dir=-1)
    dir = 1 if antardhasa_option in [1, 3, 5] else -1
    retval = Dict()
    for i in range(9):
        retval[lord] = start_date
        factor = (
            vimsottari_dict[lord]
            * vimsottari_dict[maha_lord]
            / human_life_span_for_vimsottari_dhasa
        )
        start_date += factor * year_duration
        lord = vimsottari_next_adhipati(lord, dir)

    return retval


# North Indian tradition: dasa-antardasa-pratyantardasa
# South Indian tradition: dasa-bhukti-antara-sukshma
def _vimsottari_antara(maha_lord, bhukti_lord, start_date):
    """Compute all antaradasas from given bhukit's start date.
    The bhukti's lord and its lord (mahadasa lord) must be given"""
    lord = bhukti_lord
    retval = Dict()
    for i in range(9):
        retval[lord] = start_date
        factor = vimsottari_dict[lord] * (
            vimsottari_dict[maha_lord] / human_life_span_for_vimsottari_dhasa
        )
        factor *= vimsottari_dict[bhukti_lord] / human_life_span_for_vimsottari_dhasa
        start_date += factor * year_duration
        lord = vimsottari_next_adhipati(lord)

    return retval


def _where_occurs(jd, some_dict):
    """Returns minimum key such that some_dict[key] < jd"""
    # It is assumed that the dict is sorted in ascending order
    # i.e. some_dict[i] < some_dict[j]  where i < j
    for key in reversed(some_dict.keys()):
        if some_dict[key] < jd:
            return key


def compute_vimsottari_antara_from(jd, mahadashas):
    """Returns antaradasha within which given `jd` falls"""
    # Find mahadasa where this JD falls
    i = _where_occurs(jd, mahadashas)
    # Compute all bhuktis of that mahadasa
    bhuktis = _vimsottari_bhukti(i, mahadashas[i])
    # Find bhukti where this JD falls
    j = _where_occurs(jd, bhuktis)
    # JD falls in i-th dasa / j-th bhukti
    # Compute all antaras of that bhukti
    antara = _vimsottari_antara(i, j, bhuktis[j])
    return (i, j, antara)


def vimsottari_sookshma(maha_lord, bhukti_lord, antara_lord, start_date):
    """Compute all pratyantardasas (sub-sub periods) starting from a given antara start date.
    Needs maha dasa lord, bhukti lord, antara lord, and the start date."""
    lord = antara_lord
    retval = Dict()
    for i in range(9):
        retval[lord] = start_date
        factor = (
            vimsottari_dict[lord]
            * (vimsottari_dict[maha_lord] / human_life_span_for_vimsottari_dhasa)
            * (vimsottari_dict[bhukti_lord] / human_life_span_for_vimsottari_dhasa)
            * (vimsottari_dict[antara_lord] / human_life_span_for_vimsottari_dhasa)
        )
        start_date += factor * year_duration
        lord = vimsottari_next_adhipati(lord)
    return retval


def get_vimsottari_dhasa_bhukthi(
    jd,
    place,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    use_rasi_bhukthi_variation=False,
    include_antardhasa=True,
    include_sookshma=True,  # ✅ renamed
    include_pratyantara=None,  # ✅ backward-compat alias
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=3,
    antardhasa_option=1,
    dhasa_starting_planet=1,
):
    """
    Provides Vimshottari: Mahadasha → Bhukti (Antardasha) → Antara → (optional) Sūkṣma.
    Returns flat rows suitable for parsing.

    Returns:
      - if include_sookshma=True:
          [maha, bhukti, antara, sookshma, start_date]
      - elif include_antardhasa=True (but include_sookshma=False):
          [maha, bhukti, antara, start_date]
      - else:
          [maha, start_date]

    Notes on terminology:
      North: Dasha → Antardasha → Pratyantardasha → Sūkṣma → Prāṇa
      South: Dasha → Bhukti → Antara → Sūkṣma → Prāṇa
    """
    global human_life_span_for_vimsottari_dhasa

    # Back-compat: if caller still passes include_pratyantara, treat it as include_sookshma
    if include_pratyantara is not None:
        include_sookshma = bool(include_pratyantara)

    _dhasa_cycles = 1
    _tribhagi_factor = 1
    if use_tribhagi_variation:
        _tribhagi_factor = 1.0 / 3.0
        _dhasa_cycles = int(_dhasa_cycles / _tribhagi_factor)
        human_life_span_for_vimsottari_dhasa *= _tribhagi_factor
        for k, v in vimsottari_dict.items():
            vimsottari_dict[k] = round(v * _tribhagi_factor, 2)

    dashas = vimsottari_mahadasa(
        jd,
        place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        seed_star=seed_star,
        dhasa_starting_planet=dhasa_starting_planet,
    )

    dhasa_bhukthi = []
    for _ in range(_dhasa_cycles):
        for maha_lord in dashas:
            if include_antardhasa:
                if use_rasi_bhukthi_variation:
                    from jhora.horoscope.chart import charts

                    planet_positions = charts.divisional_chart(
                        jd, place, divisional_chart_factor=1
                    )
                    maha_lord_rasi = planet_positions[maha_lord + 1][1][0]
                    bhuktis = _vimsottari_rasi_bhukthi(
                        maha_lord, maha_lord_rasi, dashas[maha_lord]
                    )
                else:
                    bhuktis = _vimsottari_bhukti(
                        maha_lord,
                        dashas[maha_lord],
                        antardhasa_option=antardhasa_option,
                    )

                for bhukti_lord in bhuktis:
                    antaras = _vimsottari_antara(
                        maha_lord, bhukti_lord, bhuktis[bhukti_lord]
                    )

                    for antara_lord in antaras:
                        if include_sookshma:
                            sookshmas = vimsottari_sookshma(
                                maha_lord,
                                bhukti_lord,
                                antara_lord,
                                antaras[antara_lord],
                            )
                            for sookshma_lord in sookshmas:
                                y, m, d, h = utils.jd_to_gregorian(
                                    sookshmas[sookshma_lord]
                                )
                                date_str = "%04d-%02d-%02d %s" % (
                                    y,
                                    m,
                                    d,
                                    utils.to_dms(h, as_string=True),
                                )
                                #            maha       bhukti      antara       sūkṣma
                                dhasa_bhukthi.append(
                                    [
                                        maha_lord,
                                        bhukti_lord,
                                        antara_lord,
                                        sookshma_lord,
                                        date_str,
                                    ]
                                )
                        else:
                            y, m, d, h = utils.jd_to_gregorian(antaras[antara_lord])
                            date_str = "%04d-%02d-%02d %s" % (
                                y,
                                m,
                                d,
                                utils.to_dms(h, as_string=True),
                            )
                            dhasa_bhukthi.append(
                                [maha_lord, bhukti_lord, antara_lord, date_str]
                            )
            else:
                jd1 = dashas[maha_lord]
                y, m, d, h = utils.jd_to_gregorian(jd1)
                date_str = "%04d-%02d-%02d %s" % (
                    y,
                    m,
                    d,
                    utils.to_dms(h, as_string=True),
                )
                dhasa_bhukthi.append([maha_lord, date_str])

    return dhasa_bhukthi


"------ main -----------"
if __name__ == "__main__":
    from jhora.tests import pvr_tests

    pvr_tests._STOP_IF_ANY_TEST_FAILED = False
    pvr_tests.vimsottari_tests()
