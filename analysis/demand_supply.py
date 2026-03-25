"""
Demand/Supply Zone Detection — identifies key support/resistance zones
from historical price-volume data using volume-weighted clustering.
"""
import pandas as pd
import numpy as np
from typing import List, Tuple
from data.models import DemandSupplyZone


def find_demand_zones(df: pd.DataFrame, num_zones: int = 3,
                      lookback: int = 100) -> List[DemandSupplyZone]:
    """
    Find demand (support) zones from price-volume data.
    Demand zones are price ranges where buying volume historically concentrated.
    
    Method:
    1. Identify candles where close > open (bullish) with above-average volume
    2. Cluster these price levels using volume-weighted binning
    3. Return top N zones ranked by volume concentration
    """
    data = df.tail(lookback).copy()
    if len(data) < 10:
        return []

    # Find bullish candles with strong volume
    avg_volume = data["volume"].mean()
    bullish = data[(data["close"] > data["open"]) & (data["volume"] > avg_volume * 0.8)]

    if bullish.empty:
        return []

    return _cluster_zones(bullish, "demand", num_zones, data["close"].iloc[-1])


def find_supply_zones(df: pd.DataFrame, num_zones: int = 3,
                      lookback: int = 100) -> List[DemandSupplyZone]:
    """
    Find supply (resistance) zones from price-volume data.
    Supply zones are price ranges where selling volume historically concentrated.
    """
    data = df.tail(lookback).copy()
    if len(data) < 10:
        return []

    avg_volume = data["volume"].mean()
    bearish = data[(data["close"] < data["open"]) & (data["volume"] > avg_volume * 0.8)]

    if bearish.empty:
        return []

    return _cluster_zones(bearish, "supply", num_zones, data["close"].iloc[-1])


def _cluster_zones(candles: pd.DataFrame, zone_type: str,
                   num_zones: int, current_price: float) -> List[DemandSupplyZone]:
    """Cluster price levels into zones using volume-weighted binning."""
    # Use the low for demand, high for supply as the key price
    if zone_type == "demand":
        prices = candles["low"].values
    else:
        prices = candles["high"].values

    volumes = candles["volume"].values

    # Create price bins
    price_range = prices.max() - prices.min()
    if price_range == 0:
        return []

    num_bins = min(num_zones * 3, max(5, len(prices) // 3))
    bin_edges = np.linspace(prices.min(), prices.max(), num_bins + 1)

    zones = []
    for i in range(num_bins):
        mask = (prices >= bin_edges[i]) & (prices < bin_edges[i + 1])
        if not mask.any():
            continue

        bin_volume = volumes[mask].sum()
        bin_low = bin_edges[i]
        bin_high = bin_edges[i + 1]
        avg_vol = volumes.mean()

        strength = min(100, (bin_volume / (avg_vol * mask.sum() + 1)) * 50)

        zones.append(DemandSupplyZone(
            zone_type=zone_type,
            price_low=round(bin_low, 2),
            price_high=round(bin_high, 2),
            strength=round(strength, 1),
            volume_concentration=round(bin_volume, 0),
        ))

    # Sort by volume concentration and return top N
    zones.sort(key=lambda z: z.volume_concentration, reverse=True)

    # Filter: demand zones below current price, supply zones above
    if zone_type == "demand":
        zones = [z for z in zones if z.price_high <= current_price * 1.01]
    else:
        zones = [z for z in zones if z.price_low >= current_price * 0.99]

    return zones[:num_zones]


def get_nearest_demand(zones: List[DemandSupplyZone],
                       current_price: float) -> Tuple[float, float]:
    """Get the nearest demand zone below current price."""
    demand = [z for z in zones if z.zone_type == "demand" and z.price_high <= current_price]
    if not demand:
        return (0.0, 0.0)
    nearest = max(demand, key=lambda z: z.price_high)
    return (nearest.price_low, nearest.price_high)


def get_nearest_supply(zones: List[DemandSupplyZone],
                       current_price: float) -> Tuple[float, float]:
    """Get the nearest supply zone above current price."""
    supply = [z for z in zones if z.zone_type == "supply" and z.price_low >= current_price]
    if not supply:
        return (0.0, 0.0)
    nearest = min(supply, key=lambda z: z.price_low)
    return (nearest.price_low, nearest.price_high)
