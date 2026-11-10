"""Ask JLCPCB how many of each BOM part it has in stock today.

Usage: jlc_stock.py fab/BOM.csv [boards]

Run it before placing an order. It is not part of the build, because the answer
changes daily and needs the network. `boards` is how many boards you mean to
have assembled (default 10); a line is flagged when stock is under five times
what that needs.
"""
import csv
import json
import sys
import urllib.request

SEARCH = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
MARGIN = 5
SENT_IN = "C99"            # JLCPCB's numbers for parts that customers send in begin with this


def lookup(lcsc):
    """(part number, maker, stock, basic or extended) for an LCSC number, or None if JLCPCB does not list it."""
    body = json.dumps({"keyword": lcsc, "currentPage": 1, "pageSize": 5}).encode()
    request = urllib.request.Request(SEARCH, data=body, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        rows = (json.load(response).get("data") or {}).get("componentPageInfo", {}).get("list") or []
    for row in rows:
        if row.get("componentCode") == lcsc:
            kind = "basic" if row.get("componentLibraryType") == "base" else "extended"
            return row.get("componentModelEn"), row.get("componentBrandEn"), int(row.get("stockCount") or 0), kind
    return None


def main():
    boards = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    with open(sys.argv[1], newline="") as fh:
        lines = list(csv.DictReader(fh))
    short = 0
    for line in lines:
        lcsc = line["LCSC Part #"]
        if not lcsc:
            print(f"{'':10} {line['Designator']:24} {line['Comment']}: NO PART NUMBER, so JLCPCB cannot place it")
            short += 1
            continue
        if lcsc.startswith(SENT_IN):
            print(f"{lcsc:10} {line['Designator'][:24]:24} {line['Comment']}: JLCPCB places it from stock you send them, {int(line['Qty']) * boards} needed")
            continue
        found = lookup(lcsc)
        need = int(line["Qty"]) * boards
        if found is None:
            print(f"{lcsc:10} {line['Designator']:24} NOT LISTED by JLCPCB")
            short += 1
            continue
        part, maker, stock, kind = found
        flag = "" if stock >= MARGIN * need else "   <-- SHORT"
        short += bool(flag)
        print(f"{lcsc:10} {line['Designator'][:24]:24} {stock:>9} in stock, {kind:8} {part} ({maker}){flag}")
    print(f"{short} of {len(lines)} lines short or unlisted for {boards} boards")


if __name__ == "__main__":
    main()
