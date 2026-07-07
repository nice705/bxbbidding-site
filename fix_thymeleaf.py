import json, re

with open("data/bids-detail.json", "r") as f:
    data = json.load(f)
bids = data["bids"] if isinstance(data, dict) else data

fixed = 0
for b in bids:
    c = b.get("content", "") or ""
    if "th:text" not in c and "th:if" not in c:
        continue

    # Decode HTML entities to make real HTML
    c = c.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    # Remove Thymeleaf attributes from tags
    c = re.sub(r'\s+th:[a-zA-Z]+="[^"]*"', "", c)
    c = re.sub(r"\s+th:[a-zA-Z]+='[^']*'", "", c)
    c = re.sub(r"\s+th:[a-zA-Z]+=\${[^}]*}", "", c)

    # Remove standalone Thymeleaf expressions
    c = re.sub(r"\${[^}]*}", "", c)

    # Remove empty elements (were only template placeholders)
    c = re.sub(r"<td[^>]*>\s*</td>", "", c)
    c = re.sub(r"<th[^>]*>\s*</th>", "", c)

    # Remove empty rows
    c = re.sub(r"<tr[^>]*>\s*</tr>", "", c)

    # Remove HTML comments
    c = re.sub(r"<!--.*?-->", "", c, flags=re.DOTALL)

    # Clean consecutive whitespace
    c = re.sub(r"\n\s*\n\s*\n", "\n\n", c)
    c = re.sub(r">\s+<", ">\n<", c)

    b["content"] = c.strip()
    fixed += 1

print(f"Fixed: {fixed} entries")

with open("data/bids-detail.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
print("Saved!")

# Verify
for b in bids:
    if "烟台大学" in b.get("title", ""):
        c2 = b["content"]
        print(f"\nVerified: {b['title']}")
        print(f"  Content length: {len(c2)}")
        print(f"  Has th:text: {'th:text' in c2}")
        print(f"  First 200: {c2[:200]}")
        break
