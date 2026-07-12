# Ticket: Reject Duplicate Channel Producers in Pipeline Validation

**Created:** 2026-07-10
**Priority:** Medium (silent-wrong-answer class, but requires a config error to trigger)
**Type:** Bug (latent) / Validation gap
**Status:** Open

### Overview

A pipeline's channel namespace is flat and single-writer by assumption: every
channel is expected to have exactly one producer. TEAx never enforces this.
Two modules declaring outputs to the same channel is accepted silently, and
the pipeline runs to completion with order-dependent results. Duplicate
producers should be a configuration error caught by validation, before
execution, like every other wiring mistake.

### Evidence

The single-writer assumption is unchecked at three layers:

1. **Graph build.** Providers are collected into a plain dict —
   `channel_providers[binding.channel_name] = module.key` — so a duplicate
   producer silently overwrites the first
   (`packages/teax-simkit/simkit/core/pipeline_graph.py:36-40`). Dependency
   edges are then drawn to an arbitrary one of the two producers
   (`pipeline_graph.py:48-59`).
2. **Validation.** Channel-type collection has the same overwrite, so input
   type checks may validate consumers against whichever producer happened to
   be iterated last (`pipeline_validator.py:144-153`).
3. **Runtime.** `context.set_channel` overwrites unconditionally; the last
   writer in topological order wins (`pipeline_executor.py:209,223`).

EntryPoint modules are in the same namespace: the parser synthesizes a
producer binding per entry input, with the input key as the channel name
(`pipeline_schema.py:219-231`), so an entry input can also collide with a
module output.

Nothing protects against this upstream by contract: channel names are chosen
freely by the config author. sysml-codegen happens to be collision-free by
construction (channels are SysML qualified names,
`sysml-codegen/src/sysml_codegen/core/qualified_names.py:30-32`), but
hand-written YAML has no such guarantee.

### Failure scenario

Two modules both declare `outputs: ...: RootModel[float] shared_channel`.
Validation passes. Consumers of `shared_channel` receive whichever value was
computed later in the topological order; the dependency graph may not even
order both producers before the consumer, since only one produced the edge.
An ExitPoint persisting `shared_channel` writes the surviving value. No
error, no warning — just a wrong number in the artifact.

### Expected behavior

- A channel with more than one producer (module output or synthesized entry
  output) fails pipeline validation before any module runs.
- The error names the channel and **both** module keys, in the style of the
  existing actionable wiring errors (`Unresolved channels detected: ...`).

### Suggested fix

One membership check at provider collection
(`pipeline_graph.py:40`): if the channel already has a provider, raise
`PipelineGraphError` with both module keys. Mirror the check (or rely on the
graph builder) in `PipelineValidator` so the failure surfaces through
`PipelineValidationError` with the standard module/details payload.

### Acceptance criteria

- Module–module duplicate producer fails pre-run with both module keys named.
- EntryPoint-input vs. module-output collision fails the same way.
- Self-consumption and unresolved-channel errors are unchanged.
- Existing test suites (simkit + battery demo) stay green — no legitimate
  pipeline relies on multi-writer channels (the bundle pattern uses distinct
  channels per output).

### Out of scope

- Channel naming conventions or namespacing (author-owned by design).
- Any change to ExitPoint bindings — exits are consumers, not producers
  (already skipped at `pipeline_graph.py:37-38`).

### Origin

Found 2026-07-10 while tracing channel-name ownership for the ExitPoint
persistence contract (`.project/concepts/exitpoint-persistence-contract.md`).
Independent of that contract change; can land in any order relative to it.
