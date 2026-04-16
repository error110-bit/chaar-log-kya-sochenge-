#!/usr/bin/env python3
import json

data = json.load(open('internships_latest.json'))
print(f'\n📊 INTERNSHIPS DATA SUMMARY')
print(f'{"="*50}')
print(f'Total internships: {data["total"]}')
print(f'Unique sources: {len(data["sources"])}')
print(f'Sources: {", ".join(data["sources"])}')
print(f'\n📈 BREAKDOWN BY TIER:')
print(f'  Tier 1 (6h): {data["tier_summary"]["tier_1"]["count"]} entries')
print(f'  Tier 2 (12h): {data["tier_summary"]["tier_2"]["count"]} entries')
print(f'  Tier 3 (24h): {data["tier_summary"]["tier_3"]["count"]} entries')
print(f'{"="*50}\n')
