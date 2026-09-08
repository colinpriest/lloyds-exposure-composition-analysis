"""What the extraction models themselves said about the basis of the recorded
prior-year development figure.

The prompt defines ``prior_year_development_gbp_m`` as the gross movement, and
``run_analysis.pyd_basis`` treats that as the basis when nothing structured says
otherwise: a pipeline override carries its triangle's basis, the adjudication register
carries an editor decision, a net claims triangle carries net, and everything else
falls to the prompt default. The 7 September 2026 review showed that default reaching
past contrary evidence the record already held. Three donors carried net development in
a sample the manuscript defines as gross:

  1206/2019  -1.0    "Prior year development figure is net of reinsurance as a gross
                      figure was not explicitly stated"        (Note 9, net claims outstanding)
  780/2017   -1.5    "Prior year development is reported as a net figure of -1.5m USD"
  457/2016  -40.3    the second model: the filing "does not unambiguously label this
                      amount as gross or net"                  (Note 16, net technical result)

This module reads those declarations. It is deliberately narrow: a note that merely
mentions a net figure is not a statement about the recorded one, and three real
patterns would otherwise be misread.

  Contrast. Many notes name a net narrative figure only to explain that they recorded
  the gross triangle value instead ("the prior_year_development_gbp_m is calculated
  from the gross claims development triangle as the narrative only provides a net prior
  year movement", 1218/2022). Only a declaration whose subject is the recorded figure
  counts, and a positive gross declaration is recognised as well.

  A quoted amount that is not the recorded value. 3000/2022 records 112.626 under a
  note reporting "a net release of GBP 25.4m". The note describes a different number,
  so it does not establish the recorded figure's basis; what it establishes is that the
  record's own provenance is inconsistent. That is ``inconsistent``, and the basis is
  unknown rather than net.

  The other model. For 457/2016 the canonical block prioritises an explicit narrative
  figure and only the second block, reporting the same value, records that the filing
  does not label it. Every block reporting the recorded value is read and the strongest
  contrary declaration wins.

The patterns are wordings, not the three quotes: the unstated rule matches any
sentence saying the filing does not label, state or identify the amount as gross or
net, and a rejected net figure ("the net figure was not used") is recognised only
where the rejection governs the net figure itself, so a net declaration that mentions
some other value not being used is still read as net. ``audit_pyd_basis.py`` writes
every declaration the corpus triggers, with the rule that fired and the sentence, so
the rule is checked on the whole corpus and not on the audited three.

Gross is still the default where no block says anything: this module reports contrary
evidence, it does not confirm a basis.
"""
import re

# the recorded figure, named as the subject of a sentence
_SUBJ = (r"(?:prior[- ]?year development(?: figure| amount| percentage)?|"
         r"prior[- ]?year movement|`?prior_year_development_gbp_m`?|"
         r"the (?:recorded|reported|stated) figure|\bpyd\b)")

# the subject as subject: "the LOB movements for prior year development are net" is
# about the class breakdown
_G = r"(?:[^.]|\.(?=\d))"
_SUBJ_LEAD = r"(?<!\bfor )(?<!\bof )(?<!\bin )(?<!\bon )(?<!\bto )(?<!\bby )" + _SUBJ
# a qualifier between the subject and its verb: "figure of GBP 5.2m", "amount ($8.8m)",
# "figure for '2019 and prior years of account'"
_QUAL = rf"(?:\s+(?:figure|amount|value))?(?:\s+\([^)]{{0,30}}\))?(?:\s+(?:of|for|in)\s+(?:(?!\b(?:lob|lobs|line|lines|class|classes|division|segment)\b){_G}){{0,60}}?)?"
_HEDGE = r"(?:(?:likely|probably|explicitly|also|therefore|thus|clearly|presumably|apparently)\s+)?"
_NET_NOUN = (r"(?:figure|value|amount|movement|development|deterioration|release|strengthening|"
             r"improvement|surplus|deficit|reduction|number|decrease|increase|profit|loss|result)")
# a gap that does not cross a negation or the other basis word
_NOT_GROSS = rf"(?:(?!\bgross\b){_G}){{0,80}}"
_PLAIN = r"(?:(?!\bno\b)(?!\bnot\b)(?!\bnet\b)(?!\bonly\b)(?:[^.;]|\.(?=\d))){0,60}"

_DECLARED_NET = [
    # 0 the recorded figure, named as subject, is (stated / reported / assumed to be) net
    rf"{_SUBJ_LEAD}{_QUAL}\s+(?:is|was|are|has been|have been|thus reported is|therefore is)\s+{_HEDGE}"
    r"(?:(?:reported|stated|presented|quoted|disclosed|shown|described|expressed|given|"
    r"labell?ed|assumed to be|believed to be|expected to be|likely to be|taken to be)\s+)?"
    r"(?:as\s+)?(?:a\s+|the\s+)?net\b",
    # 1 "... is likely NET of reinsurance"
    rf"{_SUBJ_LEAD}{_G}{{0,60}}\b(?:is|was|are)\s+(?:likely\s+|probably\s+|explicitly\s+)?NET\s+of\s+reinsurance",
    # 2
    rf"{_SUBJ_LEAD}\s+is\s+calculated\s+based\s+on\s+the\s+net\b",
    # 3
    rf"{_SUBJ_LEAD}{_G}{{0,60}}taken from\s+(?:the\s+)?(?:\w+\s+){{0,3}}?net\s+(?:{_NET_NOUN}|provisions?|claims|table|column|note|reconciliation|triangle)\b",
    # 4 "prior_year_development_gbp_m uses the NET figure as a fallback"
    rf"{_SUBJ_LEAD}{_G}{{0,40}}\b(?:uses?|used|adopts?|adopted|takes?|took|reflects?|represents?|constitutes?|equals?)\s+"
    r"(?:the\s+|this\s+|that\s+|only\s+)?(?:\w+\s+){0,2}?net\b",
    # 5 "the prior_year_development_gbp_m value is the narrated NET release"
    rf"{_SUBJ_LEAD}{_G}{{0,30}}\bis\s+the\s+(?:\w+\s+){{0,2}}?net\s+{_NET_NOUN}\b",
    # 6 the net figure is the one that was used ("this NET figure has been used")
    rf"\b(?:the|this|that|a|an|only a)\s+(?:\w+\s+){{0,2}}?net\s+(?:{_NET_NOUN}|prior[- ]year\s+\w+)"
    rf"{_NOT_GROSS}\b(?:has been|have been|is|was|were)\s+(?:\w+\s+and\s+)?(?:used|adopted|taken|recorded)\b",
    # 7 "a NET figure was used and flagged", "(used here as fallback)"
    rf"\bnet\b{_NOT_GROSS}\b(?:used|adopted|taken|recorded)\s+(?:here\s+)?as\s+(?:a\s+|the\s+)?(?:fallback|last[- ]resort|proxy)",
    # 8
    r"\bused the net (?:figure|movement|development|release|amount|value)",
    # 9 "presents the prior year movement as a NET release"
    rf"\b(?:presents?|reports?|states?|shows?|describes?|quotes?|labels?|discloses?|records?)\s+(?:the\s+)?{_SUBJ}\s+as\s+(?:a\s+|the\s+)?net\b",
    # 10 "net prior year development figures ... were converted to USD"
    rf"\bnet\s+{_SUBJ}(?:\s+figures?)?{_G}{{0,40}}\b(?:were|was|have been|has been|is|are)\s+(?:then\s+)?(?:converted|used|taken|recorded|adopted)\b",
    # 11 "... implying it is a net figure"
    rf"{_SUBJ_LEAD}{_G}{{0,100}}\b(?:implying|suggesting|indicating|meaning)\s+(?:that\s+)?(?:it|this|the figure|the amount)\s+is\s+(?:a\s+)?net\b",
    # 12 "... appears to be a net figure"
    rf"{_SUBJ_LEAD}{_G}{{0,80}}\b(?:appears?|seems?)\s+to\s+be\s+(?:a\s+)?net\b",
    # 13 "... is likely a net figure"
    rf"{_SUBJ_LEAD}{_G}{{0,80}}\b(?:is|was)\s+(?:likely|probably|presumably|apparently|therefore|thus)\s+(?:a\s+)?net\s+{_NET_NOUN}\b",
    # 14 "reported ... as a deterioration in the net provisions"
    rf"{_SUBJ_LEAD}{_G}{{0,80}}\b(?:in|within|from)\s+the\s+net\s+(?:provisions?|claims outstanding|technical provisions|column|table|reconciliation)\b",
    # 15 the figure comes from a net triangle
    r"\bnet\s+(?:claims\s+)?development\s+(?:triangle|table)\s+(?:calculation|computation|derivation|figures?|result)|"
    r"(?:calculated|computed|derived|taken)\s+from\s+(?:the\s+)?(?:\w+\s+){0,2}?net\s+(?:claims\s+)?(?:development\s+)?(?:triangle|table)|"
    rf"(?:claims\s+)?development\s+(?:triangle|table){_G}{{0,40}}\b(?:is|was|are)\s+(?:presented\s+|shown\s+|given\s+)?(?:on\s+a\s+)?net\b",
    # 16 "the movement figure used should be treated as net-of-reinsurance"
    rf"{_SUBJ}{_G}{{0,120}}\b(?:should|must|may|can|is to)\s+be\s+(?:treated|regarded|read|taken|considered|interpreted)\s+as\s+(?:a\s+)?net\b",
]

# the filing quantifies only a net figure: a declaration about the recorded amount
# where the amount quoted beside 'net' is the recorded one (beside 'gross', the
# sentence declares it gross; a different amount is a different number)
_DECLARED_NET_BY_AMOUNT = [
    r"\b(?:states?|stated|provides?|provided|reports?|reported|quotes?|quoted|discloses?|"
    r"disclosed|presents?|presented|gives?|given|mentions?|mentioned|quantif(?:ies|ied))\s+"
    r"(?:only\s+|explicitly\s+|additionally\s+|also\s+)?(?:a|an|the|its|this)\s+(?:\w+\s+){0,2}?net\b",
    r"\bonly\s+(?:a|the)\s+(?:\w+\s+){0,2}?net\b",
    rf"\bnet\s+(?:prior[- ]year|reserve|claims?)\s+\w+{_G}{{0,20}}\bof\b",
]

# an anaphoric declaration ("this is stated as a net figure") about a figure quoted in
# the same sentence: read when that quoted amount is the recorded one
_DECLARED_NET_THIS = [
    # "the figure carried forward here, GBP 4.4m, is net"
    r"\b(?:the|this)\s+(?:figure|amount|value)\b(?:[^.]|\.(?=\d)){0,60}?\bis\s+(?:therefore\s+|thus\s+)?(?:a\s+)?net\b",
    r"\b(?:this|that|which|the latter)\s+(?:figure\s+|amount\s+)?is\s+(?:explicitly\s+)?(?:stated|reported|presented|given|quoted|described|labell?ed)\s+as\s+(?:a\s+)?net\b",
    r"\bwhich\s+is\s+(?:explicitly\s+)?(?:a\s+)?net\s+(?:figure|amount|release|movement|deficit|surplus)\b",
]

# the filing, the note or the model saying the amount's basis is not established
_GROSS_OR_NET = (r"(?:['\"]?gross['\"]?\s*(?:or|vs\.?|versus|/|and|from)\s*['\"]?net['\"]?|"
                 r"['\"]?net['\"]?\s*(?:or|vs\.?|versus|/|and|from)\s*['\"]?gross['\"]?)")
_DECLARED_UNSTATED = [
    rf"(?:does not|doesn't|did not|cannot|could not|can ?not|fails? to|without|neither)\s+"
    r"(?:un)?(?:ambiguously|clearly|explicitly|specifically|expressly)?\s*"
    r"(?:label|labell?ing|identify|state|stating|specify|indicate|say|confirm|distinguish|"
    r"disclose|clarify|differentiate|separate|split|mention|make clear|make it clear|"
    r"determine|establish|tell)"
    rf"{_G}{{0,60}}\b{_GROSS_OR_NET}\b",
    rf"not (?:explicitly |clearly |unambiguously )?(?:stated|labelled|labeled|identified|specified|clear|disclosed|"
    rf"indicated|distinguished|separated){_G}{{0,40}}(?:as )?(?:whether )?{_GROSS_OR_NET}",
    rf"(?:basis|gross/net basis|gross or net basis|net/gross basis){_G}{{0,30}}(?:is |remains |was )?"
    r"(?:not stated|unstated|unclear|ambiguous|not specified|not clear|uncertain|unknown|not confirmed|not explicit)",
    rf"{_GROSS_OR_NET}\s+(?:ambiguity|uncertainty)",
    rf"whether{_G}{{0,30}}{_GROSS_OR_NET}{_G}{{0,40}}(?:is )?(?:not|unclear|uncertain|ambiguous)",
    rf"(?:unclear|uncertain|ambiguous|not (?:clear|certain|known)){_G}{{0,40}}?\b(?:whether|if)\b{_G}{{0,60}}\b{_GROSS_OR_NET}\b",
    r"if a strictly gross figure is required",
    # "this figure may be net of reinsurance"
    rf"(?:{_SUBJ}|\b(?:these|those|this|the|that)\s+(?:\w+\s+)?(?:amounts?|figures?|values?|movements?))"
    rf"{_G}{{0,60}}\b(?:may|might|could)\s+be\s+(?:reported\s+|stated\s+|presented\s+)?net\b",
]

_DECLARED_GROSS = [
    rf"`?prior_year_development_gbp_m`?{_G}{{0,80}}\b(?:reflects|is calculated from|"
    rf"is taken from|is derived from|uses|is based on)\b{_PLAIN}\bgross\b",
    rf"{_SUBJ}{_QUAL}{_PLAIN}\bis\s+(?:the\s+|a\s+)?"
    r"(?:(?:explicitly|clearly)\s+)?(?:(?:stated|reported|presented|labell?ed)\s+(?:as\s+)?(?:a\s+|the\s+)?)?gross\b",
    rf"{_SUBJ}{_G}{{0,80}}(?:calculated|computed|derived|taken|read|estimated)\s+from\s+(?:the\s+)?(?:\w+\s+){{0,2}}?gross\b",
    rf"\bgross\b{_G}{{0,40}}\b(?:triangle|table|note|reconciliation|column)\b{_G}{{0,40}}\b(?:was|were|is)\s+(?:used|prioriti[sz]ed|taken|adopted|chosen|selected)\b",
    r"\bgross\s+(?:\w+\s+){0,3}?(?:figure|movement|value|amount)\s+(?:was|is|has been)\s+(?:used|taken|recorded|adopted|prioriti[sz]ed)\b",
]

# "a net effect of both adverse and positive developments" is the arithmetic idiom,
# not a statement about reinsurance
_NET_IDIOM = re.compile(
    r"net effect|net of both|net impact of|net result of|"
    r"net of (?:this|that|these|those|such|any|its|their|RITC|the (?:RITC|effect|impact|transaction|"
    r"movement|transfer|LPT|release|strengthening|adjustment))", re.I)
# 2488/2015: "Net PYD = -49.609 per note 5 but was NOT USED as the primary PYD field
# because it is net of reinsurance" records the gross figure and says so. A sentence
# that rejects the net figure is not a declaration that the recorded one is net. The
# rejection must govern the net figure: the net item is named, and no gross item stands
# between it and the rejecting verb, so "reported as a net amount because a gross value
# was not used" is not a rejection of the net figure.
_NET_ITEM = r"\bnet\s+(?:figure|value|amount|movement|development|release|pyd|number|prior[- ]year[^.]{0,20})"
_NOT_GROSS_GAP = r"(?:(?!\bgross\b)(?!\.\s)[^!?]){0,40}?"
_NET_REJECTED = re.compile(
    rf"{_NET_ITEM}{_NOT_GROSS_GAP}\b(?:was|were|is|has been|had been|but was)?\s*not\s+(?:been\s+)?used\b|"
    rf"{_NET_ITEM}{_NOT_GROSS_GAP}\bnot\s+(?:the\s+)?(?:primary|selected|chosen|adopted)\b|"
    rf"\bdid\s+not\s+use\b{_NOT_GROSS_GAP}{_NET_ITEM}|"
    r"\brather\s+than\s+the\s+net\b|\binstead\s+of\s+the\s+net\b",
    re.I)
_AMOUNT = re.compile(
    r"(?<![\d.])(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:m\b|million)", re.I)

_NET_RE = [re.compile(p, re.I) for p in _DECLARED_NET]
_NET_AMOUNT_RE = [re.compile(p, re.I) for p in _DECLARED_NET_BY_AMOUNT]
_NET_THIS_RE = [re.compile(p, re.I) for p in _DECLARED_NET_THIS]
_UNSTATED_RE = [re.compile(p, re.I) for p in _DECLARED_UNSTATED]
_GROSS_RE = [re.compile(p, re.I) for p in _DECLARED_GROSS]
_SUBJ_RE = re.compile(_SUBJ, re.I)
# in a sentence about the class breakdown, only the field itself is the recorded figure
_FIELD_RE = re.compile(r"`?prior_year_development_gbp_m`?|the (?:recorded|reported|stated) figure", re.I)
# a sentence about the class breakdown is about the lob_movements field, not the
# recorded total, unless it names the recorded figure itself
_LOB_CONTEXT = re.compile(
    r"\blob\b|lob_movements|lob[- ]|line[s]?[- ]of[- ]business|by class|per[- ]class|class[- ]level|"
    r"by division|divisional|per[- ]line|line[- ]by[- ]line|by segment|class-by-class|"
    r"per[- ]lob|class table|class breakdown|breakdown by|by line", re.I)
_NET_WORD = re.compile(r"\bnet\b", re.I)
_GROSS_WORD = re.compile(r"\bgross\b", re.I)

# a stronger verdict wins across blocks reporting the same value
_RANK = {"net": 3, "inconsistent": 2, "unstated": 1, "gross": 0, None: -1}

#: verdicts that leave the figure ineligible for the gross sample
NOT_GROSS = {"net": "net", "inconsistent": "unknown", "unstated": "unknown"}


def _sentences(notes):
    return re.split(r"(?<=[.!?])\s+", " ".join((notes or "").split()))


def _amounts(sentence):
    return [float(a.replace(",", "")) for a in _AMOUNT.findall(sentence)]


def _adjacent_distance(sentence, word, other, recorded, window=70):
    """How close the amounts quoted just after a mention of ``word`` come to the
    recorded figure: the segment runs from the mention to the next mention of the
    other basis word or ``window`` characters, whichever is first; None without an amount."""
    best = None
    for m in word.finditer(sentence):
        seg = sentence[m.end(): m.end() + window]
        cut = other.search(seg)
        if cut:
            seg = seg[: cut.start()]
        for a in _amounts(seg):
            d = abs(abs(a) - abs(recorded))
            best = d if best is None or d < best else best
    return best


def _basis_by_adjacent_amount(sentence, recorded):
    """'net' or 'gross' when the amount quoted beside that word is the recorded figure
    and the amount beside the other word is not (or is further from it); None otherwise."""
    if recorded is None:
        return None
    tol = max(0.01, 0.01 * abs(recorded))
    dn = _adjacent_distance(sentence, _NET_WORD, _GROSS_WORD, recorded)
    dg = _adjacent_distance(sentence, _GROSS_WORD, _NET_WORD, recorded)
    n_ok = dn is not None and dn <= tol
    g_ok = dg is not None and dg <= tol
    if n_ok and g_ok:
        return "net" if dn < dg else ("gross" if dg < dn else None)
    return "net" if n_ok else ("gross" if g_ok else None)


def _amount_conflict(sentence, recorded):
    """The sentence quotes amounts in millions and none of them is the recorded figure."""
    if recorded is None:
        return False
    amounts = _amounts(sentence)
    if not amounts:
        return False
    tol = max(0.01, 0.01 * abs(recorded))
    return not any(abs(abs(a) - abs(recorded)) <= tol for a in amounts)


def _first(rules, sentence):
    for i, r in enumerate(rules):
        if r.search(sentence):
            return i
    return None


# 382/2022: "the narrative reports a small net favourable prior year development
# (GBP 0.2m) - this is NET of reinsurance": a subject preceded by 'net' within its own
# noun phrase is the narrative's net figure, not the recorded one
_NET_BEFORE = re.compile(r"\bnet\b\W*(?:\w+\W+){0,2}$", re.I)


def _first_net(sentence):
    for i, r in enumerate(_NET_RE):
        m = r.search(sentence)
        if m and not _NET_BEFORE.search(sentence[: m.start()]):
            return i
    return None


def declaration_detail(notes, recorded):
    """(verdict, quote, rule) for one model block.

    ``verdict`` is 'net', 'inconsistent', 'unstated', 'gross' or None; ``rule`` names
    the pattern that fired ('net#3', 'unstated#0', ...) so an audit can show which
    wording each record matched.
    """
    sentences = _sentences(notes)
    for sentence in sentences:
        if _NET_IDIOM.search(sentence) or _NET_REJECTED.search(sentence):
            continue
        if _LOB_CONTEXT.search(sentence) and not _FIELD_RE.search(sentence):
            continue
        i = _first_net(sentence)
        if i is not None:
            g = _first(_GROSS_RE, sentence)
            if g is not None:
                # 1301/2017: "prior_year_development_gbp_m is taken from the gross
                # technical provisions reconciliation table, which differs from the
                # net figure (GBP 71.4m)": the recorded figure is declared gross
                return "gross", sentence[:300], "gross#%d" % g
            if _amount_conflict(sentence, recorded):
                return "inconsistent", sentence[:300], "net#%d+amount" % i
            return "net", sentence[:300], "net#%d" % i
        j = _first(_NET_AMOUNT_RE, sentence)
        if j is not None and _LOB_CONTEXT.search(sentence) is None:
            # 780/2016: "the narrative describes a net prior year reserve release of
            # $23.3m, while the ... table shows a gross prior year release of $15.6m"
            # records 15.6: the amount quoted beside 'gross' is the recorded one, so
            # the sentence declares it gross; beside 'net' it would declare it net
            side = _basis_by_adjacent_amount(sentence, recorded)
            if side == "net":
                return "net", sentence[:300], "net_amount#%d" % j
            if side == "gross":
                return "gross", sentence[:300], "gross_amount"
        k = _first(_NET_THIS_RE, sentence)
        if k is not None and _amounts(sentence) and not _amount_conflict(sentence, recorded):
            return "net", sentence[:300], "net_this#%d" % k
    for sentence in sentences:
        i = _first(_UNSTATED_RE, sentence)
        if i is None:
            continue
        # 2012/2016: "the narrative quotes 10.3m but does not state whether that is
        # gross or net; the triangle-based gross calculation yields 9.38m" records the
        # gross calculation. A gross declaration for the recorded figure in the same
        # sentence settles it; a quoted amount that is not the recorded one means the
        # sentence describes a different number, and the provenance is inconsistent.
        if _first(_GROSS_RE, sentence) is not None:
            return "gross", sentence[:300], "gross#%d" % _first(_GROSS_RE, sentence)
        if _amount_conflict(sentence, recorded):
            return "inconsistent", sentence[:300], "unstated#%d+amount" % i
        return "unstated", sentence[:300], "unstated#%d" % i
    for sentence in sentences:
        i = _first(_GROSS_RE, sentence)
        if i is not None:
            return "gross", sentence[:300], "gross#%d" % i
    return None, "", ""


def declaration(notes, recorded):
    """(verdict, quote) for one model block: 'net', 'inconsistent', 'unstated', 'gross' or None."""
    verdict, quote, _ = declaration_detail(notes, recorded)
    return verdict, quote


def record_declaration(models, recorded, tol_frac=0.01):
    """(verdict, quote, model_key) over every block that reports the recorded figure.

    ``models`` is the record's ``models`` mapping. Blocks whose own development figure
    differs from ``recorded`` describe a different number and are not read.
    """
    best, quote, who, _ = record_declaration_detail(models, recorded, tol_frac)
    return best, quote, who


def record_declaration_detail(models, recorded, tol_frac=0.01):
    """(verdict, quote, model_key, rule): ``record_declaration`` with the rule that fired.

    780/2016: one block says the table shows a gross release of $15.6m (the recorded
    figure) and the other says it used a net release of $17.1m, which it did not
    record. A gross declaration whose sentence quotes the recorded figure (the amount
    beside 'gross', or a gross provenance wording with the figure in the same
    sentence) is amount-verified. It settles the record; a block's own
    inconsistency does not outrank it, nor does another block's reading that the
    filing leaves the basis unstated (the verified reading names the basis). A net
    reading does outrank it.
    """
    best, quote, who, rule = None, "", None, ""
    verified_gross = None
    for name in sorted(models or {}):
        block = models[name]
        if not isinstance(block, dict):
            continue
        try:
            value = float(block.get("prior_year_development_gbp_m"))
        except (TypeError, ValueError):
            continue
        if recorded is None:
            continue
        if abs(value - recorded) > max(0.01, tol_frac * abs(recorded)):
            continue
        verdict, said, which = declaration_detail(block.get("data_quality_notes") or "", recorded)
        if verdict == "gross" and (which == "gross_amount"
                                   or (_amounts(said) and not _amount_conflict(said, recorded))):
            # a gross reading whose sentence quotes the recorded figure
            verified_gross = (verdict, said, name, which)
        if _RANK[verdict] > _RANK[best]:
            best, quote, who, rule = verdict, said, name, which
    if best in ("inconsistent", "unstated") and verified_gross is not None:
        return verified_gross
    return best, quote, who, rule
