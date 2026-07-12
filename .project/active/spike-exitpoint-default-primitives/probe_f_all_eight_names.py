"""Spike probe F: exercise all eight JSON-native default handler names through
OutputRouter.write_outputs (the real exit path), including falsy scalars,
and assert exact payload bytes.

Run: ~/1cfe/fusion-tea/exploration/pipeline_spike/.venv-exec/bin/python \
     probe_f_all_eight_names.py <tmp_output_dir>
"""
import sys
from pathlib import Path

from pydantic import RootModel

from simkit.config.pipeline_schema import ChannelSource, PipelineChannelBinding
from simkit.io.output_router import create_default_router

BASE = Path(sys.argv[1])

CASES = [
    # (type_name, payload, filename, expected file bytes)
    ("float", 1.25, "f.json", "1.25"),
    ("int", 2, "i.json", "2"),
    ("str", "value", "s.json", '"value"'),
    ("bool", True, "b.json", "true"),
    ("RootModel[float]", RootModel[float](1.25), "rf.json", "1.25"),
    ("RootModel[int]", RootModel[int](2), "ri.json", "2"),
    ("RootModel[str]", RootModel[str]("value"), "rs.json", '"value"'),
    ("RootModel[bool]", RootModel[bool](True), "rb.json", "true"),
    # falsy scalars must persist (produced), not be skipped
    ("float", 0.0, "f0.json", "0.0"),
    ("int", 0, "i0.json", "0"),
    ("str", "", "s0.json", '""'),
    ("bool", False, "b0.json", "false"),
]

bindings = {}
values = {}
for idx, (tname, payload, fname, _) in enumerate(CASES):
    chan = f"ch{idx}"
    bindings[chan] = PipelineChannelBinding(
        type_name=tname, channel_name=chan,
        source=ChannelSource.MODULE, destination_filename=fname)
    values[chan] = payload

router = create_default_router()
res = router.write_outputs(bindings, values, base_output_dir=BASE, run_name="probe-f")

fails = []
for artifact, (tname, payload, fname, expected) in zip(res.manifest.artifacts, CASES):
    if not artifact.produced:
        fails.append(f"{fname}: NOT produced (payload={payload!r})")
        continue
    got = (res.run_dir / fname).read_text()
    ok = got == expected
    print(f"  {tname:18s} {fname:8s} bytes={got!r:12s} expected={expected!r:12s} {'OK' if ok else 'FAIL'}")
    if not ok:
        fails.append(fname)

# wrapped-vs-bare byte identity (contract invariant)
assert (res.run_dir / "f.json").read_bytes() == (res.run_dir / "rf.json").read_bytes()
print("  wrapped-vs-bare float: byte-identical OK")

if fails:
    raise SystemExit(f"FAILURES: {fails}")
print("ALL PROBE-F CHECKS PASSED")
