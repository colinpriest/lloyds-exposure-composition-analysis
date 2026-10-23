import json
# 2024 table as printed (page 51), $'000
rows = {"first": [15865, 32368, 43731, 57359],
        "one": [57296, 107236, 107543],
        "two": [66053, 118174],
        "three": [54930]}
paid24 = [11286, 48102, 3698, 3931]
# 2023 report (page 41)
r23 = {2021: [16028, 32794, 44451], 2022: [57866, 108475], 2023: [66700]}
paid23 = [7525, 9650, 41]
# swapped reading: printed row i = underwriting year 2021+i, entries = development 0..
sw = {2021: rows["first"], 2022: rows["one"], 2023: rows["two"], 2024: rows["three"]}
print("overlay ratios (2024 printed row / 2023 report cell):")
for u in (2021, 2022, 2023):
    print(u, [round(a / b, 4) for a, b in zip(sw[u], r23[u])])
# literal reading: columns = UW years, rows = dev
lit = {2021: [rows["first"][0], rows["one"][0], rows["two"][0], rows["three"][0]],
       2022: [rows["first"][1], rows["one"][1], rows["two"][1]],
       2023: [rows["first"][2], rows["one"][2]],
       2024: [rows["first"][3]]}
print("literal overlay ratios:")
for u in (2021, 2022, 2023):
    print(u, [round(a / b, 4) for a, b in zip(lit[u], r23[u])])
M_sw = sum(sw[u][-1] - sw[u][-2] for u in (2021, 2022))
M_lit = sum(lit[u][-1] - lit[u][-2] for u in (2021, 2022))
print("M swapped", M_sw, "M literal", M_lit)
for name, d in (("swapped", sw), ("literal", lit)):
    latest = sum(v[-1] for v in d.values())
    prev = sum(v[-2] for u, v in d.items() if len(v) > 1)
    prev_all = prev + 0
    print(name, "latest total", latest)
# end-2023 diagonal and implied incurred
diag_sw = sw[2021][2] + sw[2022][1] + sw[2023][0]
diag_lit = lit[2021][2] + lit[2022][1] + lit[2023][0]
latest = sum(v[-1] for v in sw.values())
print("end-2023 diagonal swapped", diag_sw, "literal", diag_lit, "2023 report end-2023", sum(v[-1] for v in r23.values()))
print("implied incurred 2024 (ultimate basis)", latest - diag_sw, "vs accounts", 50124 + 72336, round((latest - diag_sw) / (50124 + 72336) - 1, 4))
# reserve reconciliation
print("latest - paid", latest - sum(paid24), "vs 270,989")
# 2023 control
end22 = r23[2021][1] + r23[2022][0]
end23 = sum(v[-1] for v in r23.values())
print("2023 implied incurred", end23 - end22, "accounts", 16822 + 111410, round((end23 - end22) / (16822 + 111410) - 1, 4))
print("2023 outstanding", end23 - sum(paid23))
print("2023 paid test: ", sum(paid24) - sum(paid23), "vs accounts 50124")
print("swapped per-UW M cells:", {u: (sw[u][-2], sw[u][-1], sw[u][-1] - sw[u][-2]) for u in (2021, 2022)})
print("literal per-UW M cells:", {u: (lit[u][-2], lit[u][-1], lit[u][-1] - lit[u][-2]) for u in (2021, 2022)})
print("u=2023 swapped", sw[2023][-1] - sw[2023][-2])
