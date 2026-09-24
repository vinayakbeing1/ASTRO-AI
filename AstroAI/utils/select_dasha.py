from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def filter_dasha_by_horizon(
    dasha_table: List[Dict[str, Any]],
    *,
    layers: List[str],  # which layers to include: ["MD","AD","PD","SD"]
    horizon: str = "years",  # "years" | "months" | "days"
    ref_date: Optional[datetime] = None,
    thresholds: Optional[Dict[str, int]] = None,
    flatten: bool = False,
) -> List[Dict[str, Any]]:
    """
    Filter Vimshottari dasha table by horizon window and include only selected layers,
    while preserving the nested structure (MD -> AD -> PD -> SD).
    """
    if horizon is None:
        horizon = "years"

    ref_date = ref_date or datetime.today()
    thresholds = thresholds or {"years": 5, "months": 12, "days": 30}

    # window length in days
    if horizon == "years":
        window_days = thresholds.get("years", 5) * 365
    elif horizon == "months":
        window_days = thresholds.get("months", 24) * 30
    elif horizon == "days":
        window_days = thresholds.get("days", 30)
    else:
        raise ValueError(f"Unsupported horizon: {horizon}")

    ws, we = ref_date, ref_date + timedelta(days=window_days)

    # helpers
    def _dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        return datetime.strptime(s, "%Y-%m-%d")

    def _overlaps(start: Optional[str], end: Optional[str]) -> bool:
        if not start or not end:
            return False
        s, e = _dt(start), _dt(end)
        if not s or not e:
            return False
        return not (e < ws or s > we)

    filtered_mds: List[Dict[str, Any]] = []

    for md in dasha_table:
        if not _overlaps(md.get("start"), md.get("end")):
            continue

        md_copy = {
            "mahadasha": md.get("mahadasha"),
            "start": md.get("start"),
            "end": md.get("end"),
        }

        # Initialize antardashas list if we need AD, PD, or SD levels
        if "AD" in layers or "PD" in layers or "SD" in layers:
            md_antardashas = []

            for ad in md.get("antardashas", []) or []:
                if not _overlaps(ad.get("start"), ad.get("end")):
                    continue

                ad_copy = {
                    "lord": ad.get("lord"),
                    "start": ad.get("start"),
                    "end": ad.get("end"),
                }

                # Initialize pratyantardashas list if we need PD or SD
                if "PD" in layers or "SD" in layers:
                    ad_pratyantardashas = []

                    for pd in ad.get("pratyantardashas", []) or []:
                        if not _overlaps(pd.get("start"), pd.get("end")):
                            continue

                        pd_copy = {
                            "lord": pd.get("lord"),
                            "start": pd.get("start"),
                            "end": pd.get("end"),
                        }

                        # Initialize sookshmadashas list if we need SD
                        if "SD" in layers:
                            pd_sookshmadashas = []

                            for sd in pd.get("sookshmadashas", []) or []:
                                if _overlaps(sd.get("start"), sd.get("end")):
                                    pd_sookshmadashas.append(
                                        {
                                            "lord": sd.get("lord"),
                                            "start": sd.get("start"),
                                            "end": sd.get("end"),
                                        }
                                    )

                            # Only add sookshmadashas if we found any
                            if pd_sookshmadashas:
                                pd_copy["sookshmadashas"] = pd_sookshmadashas

                        # Add PD if requested or if it has SD children
                        if "PD" in layers or pd_copy.get("sookshmadashas"):
                            ad_pratyantardashas.append(pd_copy)

                    # Only add pratyantardashas if we found any
                    if ad_pratyantardashas:
                        ad_copy["pratyantardashas"] = ad_pratyantardashas

                # Add AD if requested or if it has PD children
                if "AD" in layers or ad_copy.get("pratyantardashas"):
                    md_antardashas.append(ad_copy)

            # Only add antardashas if we found any
            if md_antardashas:
                md_copy["antardashas"] = md_antardashas

        # Keep MD only if explicitly requested, or it has children
        if "MD" in layers or md_copy.get("antardashas"):
            filtered_mds.append(md_copy)
    if flatten:
        # flatten to a single list of dashas at all requested levels
        level_type = layers[0]
        flat_list = []
        if level_type == "MD":
            flat_list.extend(filtered_mds)
            return flat_list
        elif level_type == "AD":
            for md in filtered_mds:
                flat_list.extend(
                    {"antardashas": m} for m in md.get("antardashas", []) or []
                )
            return flat_list
        elif level_type == "PD":
            for md in filtered_mds:
                for ad in md.get("antardashas", []) or []:
                    flat_list.extend(
                        {"pratyantardashas": m}
                        for m in ad.get("pratyantardashas", []) or []
                    )
            return flat_list
        elif level_type == "SD":
            for md in filtered_mds:
                for ad in md.get("antardashas", []) or []:
                    for pd in ad.get("pratyantardashas", []) or []:
                        flat_list.extend(
                            {"sookshmadashas": m}
                            for m in pd.get("sookshmadashas", []) or []
                        )
            return flat_list
    return filtered_mds


def find_current_and_next(dashas, today, level="antardasha"):
    """
    Find current and next dasha at the requested level.

    Levels:
      - "mahadasha"       → top-level
      - "antardasha"      → children of mahadasha
      - "pratyantardasha" → children of antardasha
      - "sookshmadasha"   → children of pratyantardasha
    """

    def in_range(d, date):
        start = datetime.strptime(d["start"], "%Y-%m-%d").date()
        end = datetime.strptime(d["end"], "%Y-%m-%d").date()
        return start <= date < end

    # collect all dashas at the given level (without children)
    if level == "mahadasha":
        seq = [
            {k: v for k, v in m.items() if k in ("mahadasha", "start", "end")}
            for m in dashas
        ]

    elif level == "antardasha":
        seq = [
            {k: v for k, v in a.items() if k in ("lord", "start", "end")}
            for m in dashas
            for a in m.get("antardashas", [])
        ]

    elif level == "pratyantardasha":
        seq = [
            {k: v for k, v in p.items() if k in ("lord", "start", "end")}
            for m in dashas
            for a in m.get("antardashas", [])
            for p in a.get("pratyantardashas", [])
        ]

    elif level == "sookshmadasha":
        seq = [
            {k: v for k, v in s.items() if k in ("lord", "start", "end")}
            for m in dashas
            for a in m.get("antardashas", [])
            for p in a.get("pratyantardashas", [])
            for s in p.get("sookshmadashas", [])
        ]

    else:
        raise ValueError(
            "level must be one of: mahadasha, antardasha, pratyantardasha, "
            "sookshmadasha"
        )

    # find current & next
    current, nxt = None, None
    for i, d in enumerate(seq):
        if in_range(d, today):
            current = d
            nxt = seq[i + 1] if i + 1 < len(seq) else None
            break

    return {"current": current, "next": nxt}
