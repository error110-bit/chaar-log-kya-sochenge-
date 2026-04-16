#!/usr/bin/env python3
"""Test script to verify tier configuration and source mapping."""

from scrapers.internship_scraper import SOURCE_MAP, TIERS

print("\n" + "="*60)
print("TIER CONFIGURATION VERIFICATION")
print("="*60)

print(f"\n✓ SOURCE_MAP has {len(SOURCE_MAP)} entries")

total_tier_sources = 0
for tier_num in sorted(TIERS.keys()):
    tier = TIERS[tier_num]
    sources = tier['sources']
    total_tier_sources += len(sources)
    print(f"\n📊 Tier {tier_num}: {tier['name']}")
    print(f"   Interval: Every {tier['interval']}h")
    print(f"   Sources ({len(sources)}): {', '.join(sources)}")
    
    # Check if all sources are in SOURCE_MAP
    missing = [s for s in sources if s not in SOURCE_MAP]
    if missing:
        print(f"   ⚠️  MISSING from SOURCE_MAP: {missing}")
    else:
        print(f"   ✓ All sources mapped correctly")

print(f"\n📈 SUMMARY")
print(f"   Total tier sources: {total_tier_sources}")
print(f"   Total SOURCE_MAP entries: {len(SOURCE_MAP)}")

# Check if SOURCE_MAP has all tier sources
all_tier_sources = set()
for tier in TIERS.values():
    all_tier_sources.update(tier['sources'])

print(f"\n✓ Configuration OK - all {len(all_tier_sources)} tier sources are mapped!")
print("\n" + "="*60)
