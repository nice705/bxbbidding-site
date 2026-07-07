import json, re, os

DETAIL_JSON = "data/bids-detail.json"

with open(DETAIL_JSON, "r") as f:
    data = json.load(f)
bids = data["bids"] if isinstance(data, dict) else data

fixed = 0
for b in bids:
    c = b.get("content", "") or ""

    # Skip if no Thymeleaf at all
    if "th:" not in c and "${" not in c and "&lt;td" not in c and "&lt;th" not in c:
        continue

    # Decode HTML entities to make real HTML
    c = c.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    c = c.replace("&nbsp;", " ").replace("&quot;", '"')

    # 1. Remove all elements that were purely Thymeleaf template rows
    # These are tr/td/th that contained only th:* attributes or ${} expressions
    c = re.sub(r"<tr[^>]*>\s*<td[^>]*th:[a-zA-Z]+[^>]*>[^<]*</td>\s*</tr>", "", c)
    c = re.sub(r"<tr[^>]*>\s*<th[^>]*th:[a-zA-Z]+[^>]*>[^<]*</th>\s*</tr>", "", c)

    # 2. Remove entire tr/td/th that are empty after processing
    c = re.sub(r"<tr[^>]*>\s*</tr>", "", c)
    c = re.sub(r"<td[^>]*>\s*</td>", "", c)
    c = re.sub(r"<th[^>]*>\s*</th>", "", c)

    # 3. Strip all th:* attributes from remaining tags
    c = re.sub(r'\s+th:[a-zA-Z]+="[^"]*"', "", c)
    c = re.sub(r"\s+th:[a-zA-Z]+='[^']*'", "", c)
    c = re.sub(r"\s+th:[a-zA-Z]+=\${[^}]*}", "", c)
    # Remove th:block tags entirely
    c = re.sub(r"<th:block[^>]*>", "", c)
    c = re.sub(r"</th:block>", "", c)

    # 4. Remove all ${...} expressions (including nested ones)
    c = re.sub(r"\$\{[^}]*\}", "", c)

    # 5. Remove bare ${...} without surrounding quotes
    c = re.sub(r'\s+"\$\{[^}]*\}"', "", c)
    c = re.sub(r"\s+'\$\{[^}]*\}'", "", c)

    # 6. Remove any remaining HTML comments
    c = re.sub(r"<!--.*?-->", "", c, flags=re.DOTALL)

    # 7. Clean up: remove "<!-->" 
    c = c.replace("<!-->", "")

    # 8. Remove empty span tags that were Thymeleaf placeholders
    c = re.sub(r"<span[^>]*>\s*</span>", "", c)
    c = re.sub(r"<span[^>]*></span>", "", c)

    # 9. Remove attributes that are just bare expressions (th:if/no-wrapper artifacts)
    c = re.sub(r'\s+"[^"]*\$[^"]*"', "", c)
    c = re.sub(r"\s+'[^']*\$[^']*'", "", c)

    # 10. Clean whitespace
    c = re.sub(r"\n{3,}", "\n\n", c)
    c = re.sub(r">\s+<", ">\n<", c)
    c = re.sub(r"\s+$", "", c, flags=re.MULTILINE)
    c = c.strip()

    b["content"] = c
    fixed += 1

print(f"Fixed: {fixed} entries")

with open(DETAIL_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

# Verify
for b in bids:
    if "烟台大学" in b.get("title", ""):
        c2 = b["content"]
        print(f"\nVerified: {b['title']}")
        print(f"  Length: {len(c2)}")
        print(f"  Has thymeleaf: {('th:' in c2) or ('${' in c2)}")
        text = re.sub(r"<[^>]+>", "\n", c2)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        print(f"  Lines: {len(lines)}")
        for l in lines[:20]:
            print(f"    {l[:120]}")
        break

print("\nDone!")
