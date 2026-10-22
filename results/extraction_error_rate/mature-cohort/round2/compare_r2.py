"""Compare round-2 readings: arm X against arm Y, per record. Writes compare_r2.json and prints disagreements."""
import io
import json
import os

BASE = r"D:/tmp/r62/oc/readings"


def load(arm):
    out = {}
    for i in range(1, 9):
        p = os.path.join(BASE, f"{arm}{i}", "readings.json")
        with io.open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in d.items():
            out[k] = (f"{arm}{i}", v)
    return out


def num(v, *names):
    for n in names:
        x = v.get(n)
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, dict) and isinstance(x.get("value_m"), (int, float)):
            return float(x["value_m"])
    return None


X, Y = load("X"), load("Y")
keys = sorted(set(X) | set(Y))
rows, dis = [], []
for k in keys:
    if k not in X or k not in Y:
        dis.append((k, "missing in " + ("X" if k not in X else "Y")))
        continue
    (rx, vx), (ry, vy) = X[k], Y[k]
    task = k.split("|")[1]
    r = {"key": k, "readers": [rx, ry], "verdict": [vx.get("verdict"), vy.get("verdict")]}
    if task == "aggregated_column":
        r["construction"] = [vx.get("construction"), vy.get("construction")]
        fx_, fy_ = num(vx, "rule_figure_m"), num(vy, "rule_figure_m")
        r["rule_figure_m"] = [fx_, fy_]
        same_fig = fx_ is not None and fy_ is not None and abs(fx_ - fy_) <= max(0.5, 0.01 * abs(fx_))
        if vx.get("verdict") != vy.get("verdict") or not same_fig:
            dis.append((k, r))
    else:
        px, py = num(vx, "fx_line_pct_of_R"), num(vy, "fx_line_pct_of_R")
        r["pct"] = [px, py]
        same = (px is None and py is None) or (px is not None and py is not None and abs(px - py) <= 0.3)
        if vx.get("verdict") != vy.get("verdict") or not same:
            dis.append((k, r))
    rows.append(r)
with io.open(os.path.join(BASE, "compare_r2.json"), "w", encoding="utf-8", newline="") as fh:
    fh.write(json.dumps({"rows": rows, "disagreements": [d[0] for d in dis]}, indent=1) + "\n")
print("records", len(keys), "compared", len(rows), "disagreements", len(dis))
for d in dis:
    print(json.dumps(d))
from collections import Counter
print(Counter(tuple(r["verdict"]) for r in rows))
