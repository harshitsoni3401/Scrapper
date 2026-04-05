import re

with open('energy_scraper/logs/scraper_20260331_092625.log', encoding='utf-8', errors='ignore') as fh:
    content = fh.read()

# Log uses em-dash separators: 'Done — X in range │ Y deals │ Z review'
done_lines = [l.strip() for l in content.split('\n') if 'Done —' in l]

with_deals = []
zeros = []
for l in done_lines:
    m = re.search(r'\[(.+?)\]', l)
    info = re.search(r'(\d+) in range.*?(\d+) deals.*?(\d+) review', l)
    if m and info:
        name = m.group(1)
        in_range = int(info.group(1))
        deals = int(info.group(2))
        review = int(info.group(3))
        if deals > 0 or review > 0:
            with_deals.append((name, in_range, deals, review))
        else:
            zeros.append((name, in_range))

print("=== SITES WITH DEALS ===")
for name, r, d, rv in with_deals:
    print(f"  {name}: {r} in range, {d} deals, {rv} review")

print(f"\n=== ARTICLES IN RANGE BUT 0 DEALS (all rejected) ===")
for name, r in zeros:
    if r > 0:
        print(f"  *** {name}: {r} in range, 0 deals - ALL REJECTED BY AI")

print(f"\n=== SITES WITH 0 ARTICLES IN DATE RANGE ===")
for name, r in zeros:
    if r == 0:
        print(f"  {name}")
