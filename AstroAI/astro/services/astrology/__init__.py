"""
Astrology calculation services.

This package provides core astrology calculation functions,
planetary position calculations, and chart generation utilities.
"""

# Import functions lazily to avoid dependency issues
# from .astro import get_planet_positions, get_current_transit_data


def get_planet_positions(*args, **kwargs):
    """Lazy import wrapper for get_planet_positions."""
    from .astro import get_planet_positions as _get_planet_positions

    return _get_planet_positions(*args, **kwargs)


def get_current_transit_data(*args, **kwargs):
    """Lazy import wrapper for get_current_transit_data."""
    from .astro import get_current_transit_data as _get_current_transit_data

    return _get_current_transit_data(*args, **kwargs)


__all__ = ["get_planet_positions", "get_current_transit_data"]
