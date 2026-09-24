from collections import OrderedDict
import datetime
from typing import Any, Dict

from jhora.panchanga import drik
from jhora import utils
from jhora.horoscope.chart.charts import divisional_chart
from jhora.horoscope.chart import charts
from jhora.horoscope.chart.ashtakavarga import get_ashtaka_varga
from jhora.horoscope.dhasa.graha.vimsottari import (
    get_vimsottari_dhasa_bhukthi,
)
from jhora.horoscope.chart.strength import shad_bala as shadbala
from utils.select_dasha import filter_dasha_by_horizon
from astro.services.constants import DIVISIONAL_CHARTS

# Mapping indexes to planet names
PLANET_MAP = {
    0: "Sun",
    1: "Moon",
    2: "Mars",
    3: "Mercury",
    4: "Jupiter",
    5: "Venus",
    6: "Saturn",
    7: "Rahu",
    8: "Ketu",
}

# Zodiac sign names
SIGN_MAP = {
    0: "Aries",
    1: "Taurus",
    2: "Gemini",
    3: "Cancer",
    4: "Leo",
    5: "Virgo",
    6: "Libra",
    7: "Scorpio",
    8: "Sagittarius",
    9: "Capricorn",
    10: "Aquarius",
    11: "Pisces",
}


def convert_planet_positions(planet_positions):
    """
    Convert divisional_chart positions into structured JSON with lagna
    and planets. Houses are calculated relative to Lagna.
    """
    # --- find Lagna first ---
    lagna_entry = next((t for t in planet_positions if t[0] == "L"), None)
    if not lagna_entry:
        raise ValueError("Lagna not found in planet_positions")

    lagna_sign_idx, lagna_deg = lagna_entry[1]

    result = {
        "lagna": {
            "sign": SIGN_MAP[lagna_sign_idx],
            "degree": round(float(lagna_deg), 6),
        },
        "planets": [],
    }

    # defaults for retro
    default_retro = {"Rahu": True, "Ketu": True}

    for pid, (sign_idx, deg) in planet_positions:
        if pid == "L":
            continue

        name = PLANET_MAP.get(pid, f"Unknown-{pid}")
        sign_name = SIGN_MAP[sign_idx]
        house = ((sign_idx - lagna_sign_idx) % 12) + 1
        retro = default_retro.get(name, False)

        result["planets"].append(
            {
                "name": name,
                "sign": sign_name,
                "house": house,
                "degree": round(float(deg), 6),
                "retro": retro,
                "combust": False,
            }
        )

    return result


def format_shadbala(sb_response):
    """Convert Shadbala raw response into structured JSON format."""
    planet_names = [
        "Sun",
        "Moon",
        "Mars",
        "Mercury",
        "Jupiter",
        "Venus",
        "Saturn",
    ]

    sb_rupa = sb_response[7]  # Rupa values
    sb_strength = sb_response[8]  # strength ratios vs required

    result = {"shadbala": {}}

    for i, planet in enumerate(planet_names):
        rupa = sb_rupa[i]
        pct = round(sb_strength[i] * 100)  # convert ratio → %
        result["shadbala"][planet] = {"rupa": rupa, "pct_required": pct}
    return result


def format_ashtakavarga(ashtaka_response):
    """Convert Ashtakavarga raw response into structured JSON."""
    bhinna, sarvashtaka, _ = ashtaka_response

    planet_names = [
        "Sun",
        "Moon",
        "Mars",
        "Mercury",
        "Jupiter",
        "Venus",
        "Saturn",
        "Lagna",
    ]
    sign_names = [
        "Aries",
        "Taurus",
        "Gemini",
        "Cancer",
        "Leo",
        "Virgo",
        "Libra",
        "Scorpio",
        "Sagittarius",
        "Capricorn",
        "Aquarius",
        "Pisces",
    ]

    result = {
        "ashtakavarga": {
            "sarvashtakavarga": {},
            "planetary_bindus": {},
        }
    }

    # Sarvashtakavarga (total per sign)
    for i, val in enumerate(sarvashtaka):
        result["ashtakavarga"]["sarvashtakavarga"][sign_names[i]] = val

    # Planetary Bindus (Bhinna Ashtakavarga)
    for p_idx, planet in enumerate(planet_names):
        result["ashtakavarga"]["planetary_bindus"][planet] = {}
        for s_idx, val in enumerate(bhinna[p_idx]):
            sign = sign_names[s_idx]
            result["ashtakavarga"]["planetary_bindus"][planet][sign] = val

    return result


_DEFAULT_PLANET_MAP = {
    0: "Sun",
    1: "Moon",
    2: "Mars",
    3: "Mercury",
    4: "Jupiter",
    5: "Venus",
    6: "Saturn",
    7: "Rahu",
    8: "Ketu",
}


def build_vimshottari_dasha_table(
    dasha_list,
    leaf_key: str = "sookshmadashas",
    planet_map: dict | None = None,
):
    """
    Expect rows shaped exactly as: [maha, bhukti, antara, sookshma, start]
      - maha        → Mahadasha lord
      - bhukti      → Antardasha lord
      - antara      → Pratyantardasha lord
      - sookshma    → Sūkṣma lord
      - start       → "YYYY-MM-DD hh:mm:ss" (ISO-like)

        Output hierarchy:
            Mahadasha → "antardashas" (Bhuktis)
                → "pratyantardashas" (Antaras)
                → <leaf_key> (Sūkṣma list)
    """
    pmap = planet_map or _DEFAULT_PLANET_MAP
    result = {"dasha": {"system": "Vimshottari", "table": []}}
    if not dasha_list:
        return result

    # keep only strict 5-tuples and sort by start time
    rows = []
    for row in dasha_list:
        if isinstance(row, (list, tuple)) and len(row) == 5:
            m, b, a, s, start = row
            rows.append((int(m), int(b), int(a), int(s), str(start)))
    if not rows:
        return result
    rows.sort(key=lambda e: e[-1])

    # Build grouped mapping: maha -> bhukti -> antara -> {start, sookshma[]}
    maha_map: dict[int, OrderedDict[int, OrderedDict[int, dict]]] = OrderedDict()
    for m, b, a, s, start in rows:
        maha_map.setdefault(m, OrderedDict())
        maha_map[m].setdefault(b, OrderedDict())
        maha_map[m][b].setdefault(a, {"start": None, "sookshma": []})
        if maha_map[m][b][a]["start"] is None:
            maha_map[m][b][a]["start"] = start
        maha_map[m][b][a]["sookshma"].append((s, start))

    def date_only(dt_str: str | None) -> str | None:
        return dt_str.split()[0] if isinstance(dt_str, str) else None

    maha_keys = list(maha_map.keys())
    for mi, m in enumerate(maha_keys):
        bmap = maha_map[m]
        bkeys = list(bmap.keys())

        # Mahadasha start = first pratyantardasha's start in first antardasha
        maha_start = None
        for b in bkeys:
            if not bmap[b]:
                continue
            first_a = next(iter(bmap[b].keys()))
            maha_start = bmap[b][first_a]["start"]
            if maha_start:
                break

        # Mahadasha end = first pratyantardasha start in next Mahadasha (if any)
        maha_end = None
        if mi + 1 < len(maha_keys):
            nm = maha_keys[mi + 1]
            nbmap = maha_map[nm]
            for nb in nbmap:
                if not nbmap[nb]:
                    continue
                na0 = next(iter(nbmap[nb].keys()))
                maha_end = nbmap[nb][na0]["start"]
                if maha_end:
                    break

        maha_block = {
            "mahadasha": pmap.get(m, str(m)),
            "start": date_only(maha_start),
            "end": date_only(maha_end),
            "antardashas": [],  # ✅ level-2 key (Bhuktis)
        }

        # Level 2: Antardashas (Bhuktis)
        for bi, b in enumerate(bkeys):
            amap = bmap[b]
            akeys = list(amap.keys())
            if not akeys:
                continue

            # Antardasha start = first pratyantardasha start
            antarda_start = amap[akeys[0]]["start"]

            # Antardasha end = next antardasha's first pratyantardasha start,
            # else mahadasha end
            if bi + 1 < len(bkeys):
                nb = bkeys[bi + 1]
                nb_amap = bmap[nb]
                if nb_amap:
                    nb_akeys = list(nb_amap.keys())
                    antarda_end = nb_amap[nb_akeys[0]]["start"]
                else:
                    antarda_end = maha_end
            else:
                antarda_end = maha_end

            antarda_block = {
                "lord": pmap.get(b, str(b)),
                "start": date_only(antarda_start),
                "end": date_only(antarda_end),
                "pratyantardashas": [],  # ✅ level-3 key (Antaras)
            }

            # Level 3: Pratyantardashas (Antaras)
            for ai, a in enumerate(akeys):
                a_start = amap[a]["start"]
                a_end = (
                    amap[akeys[ai + 1]]["start"] if ai + 1 < len(akeys) else antarda_end
                )

                a_block = {
                    "lord": pmap.get(a, str(a)),
                    "start": date_only(a_start),
                    "end": date_only(a_end),
                    leaf_key: [],  # ✅ level-4 key (Sūkṣma list)
                }

                # Level 4: Sūkṣma list
                s_list = sorted(amap[a]["sookshma"], key=lambda t: t[1])
                for si, (slord, sstart) in enumerate(s_list):
                    send = s_list[si + 1][1] if si + 1 < len(s_list) else a_end
                    a_block[leaf_key].append(
                        {
                            "lord": pmap.get(slord, str(slord)),
                            "start": date_only(sstart),
                            "end": date_only(send) if send else None,
                        }
                    )

                antarda_block["pratyantardashas"].append(a_block)

            maha_block["antardashas"].append(antarda_block)

        result["dasha"]["table"].append(maha_block)

    return result


def get_current_transit_data(
    place: "drik.Place",
    current_datetime: datetime.datetime | None = None,
    divisional_chart_factor: int = 1,
) -> Dict[str, Any]:

    """
    Generate CURRENT transit data based on the exact current date & time
    using charts.divisional_chart with current Julian Day.

    Parameters:
        place: drik.Place
        current_datetime: datetime (defaults to now)
        divisional_chart_factor: 1=Rasi, 9=Navamsa, etc.
    """
    if current_datetime is None:
        current_datetime = datetime.datetime.now()

    # Convert current datetime → JD
    jd_now = utils.julian_day_number(
        (current_datetime.year, current_datetime.month, current_datetime.day),
        (
            current_datetime.hour,
            current_datetime.minute,
            current_datetime.second,
        ),
    )

    # Get divisional chart for current transit moment
    cht = charts.divisional_chart(
        jd_now, place, divisional_chart_factor=divisional_chart_factor
    )

    # Normalize into clean format
    chart_data = convert_planet_positions(cht)

    # Planet positions
    planet_positions = {}
    for p in chart_data["planets"]:
        planet_positions.setdefault(p["name"], []).append(
            {
                "sign": p["sign"],
                "degree": round(p["degree"], 2),
                "retro": p["retro"],
            }
        )
    return {"planet_positions": planet_positions}


def get_planet_positions(birthdata: dict) -> Dict[str, Any]:
    """
    Convert structured birthdata into drik.Date, time-of-birth tuple, and
    drik.Place, then compute charts and derived tables.
    """
    dob = drik.Date(
        birthdata["DOB"]["year"],
        birthdata["DOB"]["month"],
        birthdata["DOB"]["day"],
    )

    tob = (
        birthdata["TOB"]["hour"],
        birthdata["TOB"]["min"],
        birthdata["TOB"]["sec"],
    )

    pob = birthdata["POB"]
    place = drik.Place(pob["name"], pob["lat"], pob["lon"], pob["timezone"])
    jd = utils.julian_day_number(dob, tob)
    result = {}
    for chart in DIVISIONAL_CHARTS:
        planet_positions = convert_planet_positions(
            divisional_chart(jd, place, divisional_chart_factor=int(chart[1:]))
        )
        result[chart] = planet_positions

    shad_bala = shadbala(jd, place)

    house_to_planet_list = utils.get_house_planet_list_from_planet_positions(
        divisional_chart(jd, place)
    )
    ashtaka_varga = get_ashtaka_varga(house_to_planet_list)
    vimsottari_dhasa = get_vimsottari_dhasa_bhukthi(jd, place)
    result["shadbala"] = format_shadbala(shad_bala)
    result["ashtaka_varga"] = format_ashtakavarga(ashtaka_varga)
    result["vimsottari_dhasa"] = filter_dasha_by_horizon(
        build_vimshottari_dasha_table(vimsottari_dhasa)["dasha"]["table"],
        layers=["MD", "AD", "PD", "SD"],
        thresholds={"years": 10},
    )
    return result
