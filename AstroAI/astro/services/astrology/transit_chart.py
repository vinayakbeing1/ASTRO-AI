from datetime import datetime, timezone, timedelta
from typing import Literal, Tuple
from jhora.horoscope.transit.tajaka import annual_chart, monthly_chart, sixty_hour_chart

from jhora import utils

ChartType = Literal["annual", "monthly", "day", "sixty_hour"]


def _tz_from_place(place) -> timezone:
    off = float(getattr(place, "timezone", getattr(place, "tz", 0)))  # hours, e.g., 5.5
    h = int(off)
    m = int(round(abs(off - h) * 60))
    if off < 0 and h == 0:  # handle negative minutes offsets like -3.5
        m = -m
    return timezone(timedelta(hours=h, minutes=m))


def _years_index(dob_dt: datetime, target_dt: datetime) -> int:
    y = target_dt.year - dob_dt.year
    if target_dt < dob_dt.replace(year=target_dt.year):
        y -= 1
    return max(y, 0)


def _meta_to_dt_utc(meta) -> datetime:
    # meta shape: [(y,m,d), "HH:MM:SS AM/PM"] or [(y,m,d), (h,m,s)]
    (y, m, d), hm = meta
    if isinstance(hm, (tuple, list)):
        h, mi, s = int(hm[0]), int(hm[1]), int(hm[2] if len(hm) > 2 else 0)
    else:
        # "HH:MM:SS AM/PM" → 24h
        t, ap = hm.split()
        h, mi, s = map(int, t.split(":"))
        if ap.upper().startswith("P") and h != 12:
            h += 12
        if ap.upper().startswith("A") and h == 12:
            h = 0
    return datetime(y, m, d, h, mi, s, tzinfo=timezone.utc)


def _month_index_by_sampling(
    jd_at_dob: float, place, years: int, target_dt: datetime
) -> int:
    t_utc = target_dt.astimezone(timezone.utc)
    starts = []
    for k in range(1, 14):  # 12 boundaries + 1 next
        _, meta = monthly_chart(jd_at_dob, place, years=years, months=k)
        starts.append(_meta_to_dt_utc(meta))
    for k in range(12):
        if starts[k] <= t_utc < starts[k + 1]:
            return k + 1
    return 12


def _sixty_index_by_sampling(
    jd_at_dob: float,
    place,
    years: int,
    month: int,
    target_dt: datetime,
    slices: int = 12,
) -> int:
    t_utc = target_dt.astimezone(timezone.utc)
    starts = []
    for n in range(1, slices + 2):  # slice boundaries + 1 next
        _, meta = sixty_hour_chart(
            jd_at_dob, place, years=years, months=month, sixty_hour_count=n
        )
        starts.append(_meta_to_dt_utc(meta))
    for n in range(slices):
        if starts[n] <= t_utc < starts[n + 1]:
            return n + 1
    return slices


def tajaka_chart_for_date(
    jd_at_dob,
    place,
    chart_type: ChartType = "annual",
    target_dt: datetime = None,
    divisional_chart_factor: int = 1,
):
    """
    Returns (chart, meta) using your existing annual_chart / monthly_chart / sixty_hour_chart.
    chart_type: "annual" | "monthly" | "day" (alias of sixty_hour) | "sixty_hour"
    target_dt defaults to 'now' in the place's timezone.
    """

    years = _years_index(dob_dt, target_dt)

    if chart_type == "annual":
        return annual_chart(
            jd_at_dob,
            place,
            divisional_chart_factor=divisional_chart_factor,
            years=years,
        )

    month = _month_index_by_sampling(jd_at_dob, place, years, target_dt)
    if chart_type == "monthly":
        return monthly_chart(
            jd_at_dob,
            place,
            divisional_chart_factor=divisional_chart_factor,
            years=years,
            months=month,
        )

    # "day" → sixty-hour chart
    sixty = _sixty_index_by_sampling(jd_at_dob, place, years, month, target_dt)
    return sixty_hour_chart(
        jd_at_dob,
        place,
        divisional_chart_factor=divisional_chart_factor,
        years=years,
        months=month,
        sixty_hour_count=sixty,
    )
