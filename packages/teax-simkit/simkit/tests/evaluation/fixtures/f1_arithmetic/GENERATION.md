# F1 Arithmetic Fixture Generation

**The reproduction route changed at CONSTRAINT-SEMANTICS Item 3, and this is the record of why.**

This fixture used to be built by `generate_fixture.py`, which assembled a `ComputationGraph`
programmatically from synthetic constraint facts and fed it to
`sysml_codegen.analysis.constraint_lowering.extend_graph_with_constraints` and
`analysis.parameter_groups.ParameterGroupDeriver`. The codegen cutover recovery
(2026-08-12) **deleted both of those modules** along with the rest of the legacy
string-resolution stack, so that construction cannot run at any current codegen revision.
Refreshing the script's stale environment pins was necessary and not sufficient: with correct
pins the preflight passes and `_build_context` then fails at
`ModuleNotFoundError: No module named 'sysml_codegen.analysis.constraint_lowering'`.

The script has been **deleted** rather than kept as something that cannot run. The three
predicates it built in code are now authored as SysML in `models/toy_plant.sysml`, and the
fixture is reproduced by the ordinary public route every other fixture uses.

## Reproducing this package

```bash
set -a; source <agentic-mbse>/.env; set +a          # SYSIDE_LICENSE_KEY
cd simkit/tests/evaluation/fixtures/f1_arithmetic
sysml-codegen generate --models models --output package_live \
    --package-name f1_arithmetic_constraints
```

No detached worktree, no pinned lockfile hash, no bespoke script. That is the point of the
change: the fixture's provenance is now a model plus a released generator, which is the same
claim every other package in this tree makes.

## What is in the package

- Generated: 2026-08-13, CONSTRAINT-SEMANTICS Item 3
- Package name: `f1_arithmetic_constraints`
- Model source: `models/toy_plant.sysml` (three asserted constraints on `part fixture`)
- Runtime contract version: `2.0.0`
- Catalog schema version: `3.0.0`
- Generator version: `0.1.0`
- sysml-codegen revision at generation: `cb7b95c6ef6a887a59eae25353496d4e7a2619ac`
- agentic-mbse revision at generation: `5088b417c9e5453271291d46cd5fb23fc0579b1e`
- Executable fingerprint: `0cd8912baae8267e48437fd8a308eaf9944fe7f5c15fadbaf85d4c54be7cb17b`
- Coverage account (baked): 3 authored / 3 applicable / 3 assessed / 0 unassessed /
  0 inapplicable / `{}` / `complete`
- Graph constraint order: `f3_nested_check, f1_division_check, f2_power_check`
- YAML module order: `entry_fusion, toy_plant__fixture__f3_nested_check__8b3352fdf1f62ba5,
  toy_plant__fixture__f1_division_check__b973058cd670a967,
  toy_plant__fixture__f2_power_check__b4ca916c6d129ce9, constraint_report_aggregator, exit_point`

## Identity that moved, and whose change it was

Two things moved that are **not** Item 3's doing. They are pre-existing drift between the
codegen revision that produced the original bytes (`512786c7…`, 2026-07-19) and codegen HEAD,
surfaced because regeneration is what makes drift visible:

- **Constraint ids** now carry the owner path and an occurrence hash
  (`f1_division_check` → `toy_plant__fixture__f1_division_check__b973058cd670a967`).
- **Entry-point keys** name the part *usage* rather than its def
  (`toy_plant__Toy_Plant__division_a` → `toy_plant__fixture__division_a`), because a
  `DESIGN_ATTRIBUTE` keys by the supplying attribute's display path (ADR-001).

The five committed `cases/*.json` and the two f1 test modules were updated for both, with the
same annotation at each site.

Item 3's own changes to this package are exactly the report ones: the `coverage` block,
`assessed_count` → `assessed_entry_count`, the five-token headline vocabulary, and
`RUNTIME_CONTRACT_VERSION` `1.0.0` → `2.0.0`.
