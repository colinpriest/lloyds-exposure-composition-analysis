yrs = [2011, 2012, 2013, 2014, 2015, 2016, 2017]
# 2017 report p25 gross (age lists, age 0 = end of UW year), 2010&prior latest 2,596,383
g17 = {2011: [196970, 370564, 366668, 371882, 365612, 361604, 355885],
       2012: [231788, 369868, 387030, 377008, 374956, 383618],
       2013: [208312, 379373, 381385, 374738, 389916],
       2014: [191952, 384779, 419551, 436548],
       2015: [186454, 467615, 550721],
       2016: [296537, 696895],
       2017: [553292]}
g16 = {2011: [203051, 374794, 361202, 361254, 351980, 345468],
       2012: [241603, 372329, 381012, 363811, 358275],
       2013: [214375, 379815, 372441, 360566],
       2014: [197872, 385327, 413612],
       2015: [240706, 471111],
       2016: [305254]}
g15 = {2011: [216533 * 0 + 186080 * 0, ], }  # placeholder, not used
prior17, prior16 = 2596383, 2539636
pay17 = {"prior": 2474465, 2011: 326721, 2012: 324985, 2013: 304092, 2014: 285779, 2015: 296081, 2016: 285709, 2017: 118207}
pay16 = {"prior": 2313681, 2011: 300155, 2012: 284493, 2013: 259142, 2014: 219182, 2015: 167061, 2016: 49647}
pay15 = {"prior": 2285654, 2011: 282009, 2012: 260657, 2013: 221175, 2014: 151209, 2015: 36214}
# 2015 report latest ult
lat15 = {"prior": 2519427, 2011: 344242, 2012: 351920, 2013: 356540, 2014: 360033, 2015: 217535}
acc17_inc = 628736 + 379802
acc16_inc = 379856 + 166053
acc17_paid, acc16_paid = 628736, 379856

print("A. end-2016 cells: 2017 table (age = n-1 for years 2011-2016) vs 2016 report latest")
tot17d = tot16l = 0
for u in range(2011, 2017):
    c17 = g17[u][-2]
    c16 = g16[u][-1]
    tot17d += c17
    tot16l += c16
    print(u, "2017 table end-2016:", c17, "| 2016 report latest:", c16, "| diff", c17 - c16, "| ratio", round(c17 / c16, 4))
print("sum", tot17d, tot16l, tot17d - tot16l, round(tot17d / tot16l - 1, 4))
print("2010&prior: 2017 latest", prior17, "2016 latest", prior16, "ratio", round(prior17 / prior16, 4), "(2017 table prints no end-2016 cell for it)")

print("\nB. age-by-age ratio 2017 table / 2016 report, same UW year")
for u in range(2011, 2017):
    print(u, [round(a / b, 3) for a, b in zip(g17[u], g16[u])])

print("\nC. M, u<=2015 (t-2), gross, 2011..2015")
for label, base in (("2017 table own end-2016 cells", {u: g17[u][-2] for u in range(2011, 2016)}),
                    ("2016 report printed latest", {u: g16[u][-1] for u in range(2011, 2016)})):
    cells = {u: (base[u], g17[u][-1], g17[u][-1] - base[u]) for u in range(2011, 2016)}
    s = sum(c[2] for c in cells.values())
    print(label, cells, "sum", s, "| with 2010&prior using 2016 printed", s + prior17 - prior16)
print("t-1 (2016) own", g17[2016][-1] - g17[2016][-2], "2016 base", g17[2016][-1] - g16[2016][-1])

print("\nD. incurred test")
latest17 = sum(g17[u][-1] for u in yrs)
print("2017 latest ex-prior", latest17)
diag16_17 = sum(g17[u][-2] for u in range(2011, 2017))
inc17_own = latest17 - diag16_17
print("implied 2017 (own diag, ex-prior)", inc17_own, "acc", acc17_inc, round(inc17_own / acc17_inc - 1, 4))
inc17_own_prior = inc17_own + (prior17 - prior16)
print("incl prior using 2016 printed prior", inc17_own_prior, round(inc17_own_prior / acc17_inc - 1, 4))
base16_print = sum(g16[u][-1] for u in range(2011, 2017))
inc17_p16 = latest17 - base16_print
print("2016 printed base, ex-prior", inc17_p16, round(inc17_p16 / acc17_inc - 1, 4))
print("2016 printed base incl prior", inc17_p16 + prior17 - prior16, round((inc17_p16 + prior17 - prior16) / acc17_inc - 1, 4))
# 2016 control: 2016 table end-2015 diag
latest16 = sum(g16[u][-1] for u in range(2011, 2017))
diag15 = sum(g16[u][-2] for u in range(2011, 2016))
inc16 = latest16 - diag15
print("2016 control implied", inc16, "acc", acc16_inc, round(inc16 / acc16_inc - 1, 4))
print("2016 table end-2015 diag vs 2015 report latest:", [(u, g16[u][-2], lat15[u], round(g16[u][-2] / lat15[u], 4)) for u in range(2011, 2016)])
print("accounts: gross earned 2017", 1138050 + 14354, "GWP 1138050; 2016 earned", 1063936 - 75959, "GWP 1063936")

print("\nE. paid proxy (end-t-1 cumulative paid taken from the PRIOR report; the year t table prints none)")
t17 = sum(pay17.values()); t16 = sum(pay16.values()); t15 = sum(pay15.values())
print("2017 cum paid", t17, "2016 cum paid", t16, "2015", t15)
print("implied 2017 paid", t17 - t16, "acc", acc17_paid, round((t17 - t16) / acc17_paid - 1, 4))
print("implied 2016 paid", t16 - t15, "acc", acc16_paid, round((t16 - t15) / acc16_paid - 1, 4))
print("per-year 2017 increments", {k: pay17[k] - pay16.get(k, 0) for k in pay17})

print("\nF. FX ceiling per brief: 2017 note p36 rates per GBP: USD 1.24->1.35, EUR 1.17->1.13, CAD 1.66->1.70")
for n, a, b in (("USD", 1.24, 1.35), ("EUR", 1.17, 1.13), ("CAD", 1.66, 1.70)):
    print(n, "GBP value of a unit-currency claim, end-2016 -> end-2017 ratio:", round(a / b, 4))
print("2015 age-0 cell ratio 2017/2016:", round(186454 / 240706, 4))
print("reserve roll-forward: opening 1,200,561 + 379,802 + FX(70,340) + other 37,196 =", 1200561 + 379802 - 70340 + 37196)
print("FX on opening reserves", round(-70340 / 1200561, 4))
print("sum latest ult incl prior 2017:", latest17 + prior17, "(table total 5,963,258)")
print("balance to pay check 2017: ult - paid =", latest17 + prior17 - t17)

print("\nG. net table M check (u 2011..2015)")
n17 = {2011: [171467, 325994, 320281, 322717, 316553, 312241, 307196],
       2012: [187895, 310024, 328051, 313252, 311802, 313074],
       2013: [168159, 331046, 346438, 355432, 368277],
       2014: [163860, 330339, 359394, 382816],
       2015: [142157, 382840, 431174]}
print("net own base", sum(n17[u][-1] - n17[u][-2] for u in n17))
n16 = {2011: 298557, 2012: 297874, 2013: 340943, 2014: 351544, 2015: 384483}
print("net 2016 base", sum(n17[u][-1] - n16[u] for u in n17))
