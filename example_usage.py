#!/usr/bin/env python3
"""
Example usage of Eclipse AI with new features.

This script demonstrates the improved decision-making capabilities including:
- Strategy profiles
- Custom weights
- Parameter tuning
- Profile comparison
"""

from eclipse_ai import recommend
from eclipse_ai.value import list_profiles, print_profile_summary


def example_basic():
    """Basic usage with improved defaults."""
    print("\n" + "="*60)
    print("Example 1: Basic Usage with Improved Defaults")
    print("="*60)
    
    result = recommend(
        "eclipse_ai/eclipse_test/board.jpg",
        "eclipse_ai/eclipse_test/tech.jpg"
    )
    
    print(f"\nTop 3 recommendations:")
    for i, plan in enumerate(result["plans"][:3], 1):
        print(f"\n  Option {i}:")
        for step in plan["steps"]:
            action = step.get("action", "Unknown")
            payload = step.get("payload", {})
            score = step.get("score")
            print(f"    {action}: score={score:.2f}")


def example_with_profile():
    """Using a strategy profile for customized behavior."""
    print("\n" + "="*60)
    print("Example 2: Using Aggressive Profile")
    print("="*60)
    
    result = recommend(
        "eclipse_ai/eclipse_test/board.jpg",
        "eclipse_ai/eclipse_test/tech.jpg",
        manual_inputs={"_profile": "aggressive"}
    )
    
    print(f"\nAggressive AI recommendations:")
    for i, plan in enumerate(result["plans"][:3], 1):
        print(f"\n  Option {i}:")
        for step in plan["steps"]:
            action = step.get("action", "Unknown")
            print(f"    {action}")


def example_high_quality():
    """High-quality decision with increased computation."""
    print("\n" + "="*60)
    print("Example 3: High-Quality Decision (more simulations)")
    print("="*60)
    
    result = recommend(
        "eclipse_ai/eclipse_test/board.jpg",
        "eclipse_ai/eclipse_test/tech.jpg",
        manual_inputs={
            "_planner": {
                "simulations": 1000,  # vs 600 default
                "depth": 4,           # vs 3 default
            }
        }
    )
    
    print(f"\nHigh-quality recommendations:")
    for i, plan in enumerate(result["plans"][:3], 1):
        print(f"\n  Option {i}:")
        for step in plan["steps"]:
            action = step.get("action", "Unknown")
            details = step.get("details", {})
            print(f"    {action}: {details}")


def example_custom_weights():
    """Using custom weight overrides."""
    print("\n" + "="*60)
    print("Example 4: Custom Weights (Science-Focused)")
    print("="*60)
    
    science_focus = {
        "_profile": "tech_rush",
        "_weights": {
            "science_income": 0.50,      # vs 0.45 in tech_rush profile
            "pink_planets": 0.85,        # vs 0.75 in profile
            "tech_count": 0.50,          # vs 0.40 in profile
        }
    }
    
    result = recommend(
        "eclipse_ai/eclipse_test/board.jpg",
        "eclipse_ai/eclipse_test/tech.jpg",
        manual_inputs=science_focus
    )
    
    print(f"\nScience-focused recommendations:")
    for i, plan in enumerate(result["plans"][:3], 1):
        print(f"\n  Option {i}:")
        for step in plan["steps"]:
            action = step.get("action", "Unknown")
            print(f"    {action}")


def example_profile_comparison():
    """Compare different profiles side-by-side."""
    print("\n" + "="*60)
    print("Example 5: Profile Comparison")
    print("="*60)
    
    profiles = ["balanced", "aggressive", "economic"]
    
    for profile_name in profiles:
        print(f"\n--- {profile_name.upper()} Profile ---")
        
        result = recommend(
            "eclipse_ai/eclipse_test/board.jpg",
            "eclipse_ai/eclipse_test/tech.jpg",
            manual_inputs={"_profile": profile_name},
            top_k=1  # Just show top recommendation
        )
        
        if result["plans"]:
            plan = result["plans"][0]
            print(f"Top action: ", end="")
            if plan["steps"]:
                action = plan["steps"][0].get("action", "Unknown")
                print(action)


def list_available_profiles():
    """Show all available profiles."""
    print("\n" + "="*60)
    print("Available Strategy Profiles")
    print("="*60)
    
    list_profiles()
    
    print("\nProfile Details:")
    print("-" * 60)
    print_profile_summary("aggressive")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print(" Eclipse AI - Example Usage with Improvements")
    print("="*70)
    
    # Show available profiles first
    list_available_profiles()
    
    # Run examples
    examples = [
        example_basic,
        example_with_profile,
        example_high_quality,
        example_custom_weights,
        example_profile_comparison,
    ]
    
    for i, example_func in enumerate(examples, 1):
        try:
            example_func()
        except Exception as e:
            print(f"\nExample {i} failed: {e}")
            print("(This is expected if board/tech images are not available)")
    
    print("\n" + "="*70)
    print(" Examples Complete!")
    print("="*70)
    print("\nFor more details, see:")
    print("  - TUNING_GUIDE.md   : Comprehensive tuning instructions")
    print("  - IMPROVEMENTS.md   : Summary of all improvements")
    print("  - README.md         : Quick start guide")
    print()


if __name__ == "__main__":
    main()

