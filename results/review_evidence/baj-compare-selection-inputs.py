import json,sys,numpy as np
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'src'))
import check_missingness_sensitivity as c
S,R,H,year,key,syndicate=c.load_sample(); ritc=c.ritc_flag(key).astype(float)
rows=c.add_size_proxies(c.classify_filings())
target=[r for r in rows if r["category"] in {"eligible_outcome_unavailable","eligible_observed_composition_unavailable","working_sample"}]
unavailable=[r for r in target if r["category"]=="eligible_outcome_unavailable"]; unresolved=[r for r in rows if r["category"]=="eligibility_unresolved"]
c.check_populations(S,rows,unresolved)
inputs, hhis, years, meta=c._pseudo_inputs(unavailable+unresolved,rows,R,H)
print(json.dumps({"sample_keys":list(key),"sample_S":S.tolist(),"sample_R":R.tolist(),"sample_H":H.tolist(),"sample_year":year.tolist(),"sample_ritc":ritc.tolist(),"target_keys":[r["file"] for r in target],"target_size":[r["size_proxy"] for r in target],"unavailable_keys":[r["file"] for r in unavailable],"unresolved_keys":[r["file"] for r in unresolved],"pseudo_R":inputs.tolist(),"pseudo_H":hhis.tolist(),"pseudo_year":years.tolist(),"pseudo_ritc":c.ritc_flag([r["file"] for r in unavailable+unresolved]).tolist()},sort_keys=True))
