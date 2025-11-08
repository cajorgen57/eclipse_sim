"""
Strategy profile management for Eclipse AI.

This module provides pre-configured weight profiles for different playstyles,
allowing easy customization of AI behavior without manual weight tuning.
"""

from __future__ import annotations
import os
from typing import Dict, Any, Optional
import yaml


_PROFILES_CACHE: Optional[Dict[str, Dict[str, float]]] = None


def load_all_profiles() -> Dict[str, Dict[str, float]]:
    """Load all strategy profiles from profiles.yaml."""
    global _PROFILES_CACHE
    if _PROFILES_CACHE is not None:
        return _PROFILES_CACHE
    
    profiles_path = os.path.join(os.path.dirname(__file__), "profiles.yaml")
    with open(profiles_path, "r", encoding="utf-8") as f:
        _PROFILES_CACHE = yaml.safe_load(f) or {}
    
    return _PROFILES_CACHE


def get_available_profiles() -> list[str]:
    """Get list of available profile names."""
    profiles = load_all_profiles()
    return sorted(profiles.keys())


def load_profile(profile_name: str) -> Dict[str, float]:
    """
    Load a specific strategy profile.
    
    Args:
        profile_name: Name of the profile (e.g., "aggressive", "economic", "balanced")
        
    Returns:
        Dictionary of weight overrides for the specified profile
        
    Raises:
        ValueError: If profile_name doesn't exist
    """
    profiles = load_all_profiles()
    
    if profile_name not in profiles:
        available = ", ".join(get_available_profiles())
        raise ValueError(
            f"Profile '{profile_name}' not found. "
            f"Available profiles: {available}"
        )
    
    return dict(profiles[profile_name])


def merge_profile_with_base(
    base_weights: Dict[str, float],
    profile_name: str
) -> Dict[str, float]:
    """
    Merge a profile's overrides with base weights.
    
    Args:
        base_weights: Base weight dictionary (typically from weights.yaml)
        profile_name: Name of profile to apply
        
    Returns:
        New dictionary with profile overrides applied to base weights
    """
    merged = dict(base_weights)
    profile_overrides = load_profile(profile_name)
    merged.update(profile_overrides)
    return merged


def get_profile_info(profile_name: str) -> Dict[str, Any]:
    """
    Get metadata about a strategy profile.
    
    Args:
        profile_name: Name of the profile
        
    Returns:
        Dictionary containing profile statistics and key characteristics
    """
    profile = load_profile(profile_name)
    
    # Analyze profile characteristics
    military_keys = [
        "fleet_power", "fleet_dreadnoughts", "fleet_cruisers",
        "dreadnought_firepower", "cruiser_firepower", "total_firepower_designs"
    ]
    economic_keys = [
        "science_income", "materials_income", "money_income",
        "orange_net_income", "colonized_planets"
    ]
    defensive_keys = [
        "fleet_starbases", "starbase_defense", "total_defense_designs",
        "threat_ratio", "contested_hexes"
    ]
    
    military_score = sum(profile.get(k, 0) for k in military_keys)
    economic_score = sum(profile.get(k, 0) for k in economic_keys)
    defensive_score = sum(abs(profile.get(k, 0)) for k in defensive_keys)
    
    return {
        "name": profile_name,
        "override_count": len(profile),
        "military_focus": round(military_score, 2),
        "economic_focus": round(economic_score, 2),
        "defensive_focus": round(defensive_score, 2),
        "key_overrides": sorted(
            [(k, v) for k, v in profile.items()],
            key=lambda x: abs(x[1]),
            reverse=True
        )[:5]  # Top 5 most significant overrides
    }


def print_profile_summary(profile_name: str) -> None:
    """Print a human-readable summary of a profile."""
    info = get_profile_info(profile_name)
    
    print(f"\n=== {info['name'].upper()} Profile ===")
    print(f"Overrides: {info['override_count']} weights")
    print(f"Military Focus: {info['military_focus']}")
    print(f"Economic Focus: {info['economic_focus']}")
    print(f"Defensive Focus: {info['defensive_focus']}")
    print(f"\nTop 5 Key Changes:")
    for key, value in info['key_overrides']:
        print(f"  {key}: {value}")


def list_profiles() -> None:
    """Print all available profiles with brief descriptions."""
    profiles = load_all_profiles()
    
    descriptions = {
        "balanced": "Default weights with no biases",
        "aggressive": "Prioritize military and territorial conquest",
        "economic": "Maximize resource generation and tech advancement",
        "tech_rush": "Focus on rapid technology acquisition",
        "defensive": "Secure borders and defensive positioning",
        "expansion": "Rapid territorial expansion and colonization",
        "late_game": "Optimize for endgame VP maximization",
        "turtle": "Extreme defensive play with minimal expansion"
    }
    
    print("\n=== Available Strategy Profiles ===\n")
    for name in sorted(profiles.keys()):
        desc = descriptions.get(name, "Custom profile")
        override_count = len(profiles[name])
        print(f"  {name:15s} - {desc} ({override_count} overrides)")
    print()


# Convenience function for main API
def apply_profile_to_weights(
    base_weights: Dict[str, float],
    profile: Optional[str] = None
) -> Dict[str, float]:
    """
    Apply a profile to base weights if specified, otherwise return base weights.
    
    Args:
        base_weights: Base weight dictionary
        profile: Optional profile name to apply
        
    Returns:
        Weights with profile applied (if specified) or base weights unchanged
    """
    if profile is None or profile.lower() in ("none", "balanced", "default"):
        return base_weights
    
    return merge_profile_with_base(base_weights, profile)


__all__ = [
    "load_profile",
    "load_all_profiles",
    "get_available_profiles",
    "merge_profile_with_base",
    "get_profile_info",
    "print_profile_summary",
    "list_profiles",
    "apply_profile_to_weights",
]

