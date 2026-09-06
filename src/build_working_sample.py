"""The loader pass that precedes the calibrations.

Every calibrator and check reads the working sample from ``model/exposure_results.json``
(``adopted_model.load_sample`` and the per-script ``load_sample`` functions take its
``observations``).  That file is written by ``run_analysis.py``, which also embeds the
fitted dispersion calibration and generates the calibration table, so it has to run
again after the fits.  Until round 52 the manifest ran ``run_analysis.py`` only at the
end: a rerun after the extraction records changed fitted every model on the previous
sample and only then rebuilt the sample (the 6 September 2026 rerun reproduced the
committed fits to the last digit while 539 input records had changed).

This step runs the loader first so the calibrations see the current records.  The
calibration-dependent blocks it writes are refreshed by ``run_analysis.py`` in the
outputs stage; the manifest-order test (``test_manifest_order.py``) checks that no step
reads an artefact a later step produces.
"""
import pathlib
import runpy
import sys

if __name__ == "__main__":
    sys.argv = ["run_analysis.py"]
    runpy.run_path(str(pathlib.Path(__file__).with_name("run_analysis.py")), run_name="__main__")
