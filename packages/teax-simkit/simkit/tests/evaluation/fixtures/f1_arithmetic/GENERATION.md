# F1 Arithmetic Fixture Generation

This is a production-equivalent sealed fixture. Synthetic constraint facts enter production
`extend_graph_with_constraints` and `assemble_constraint_catalog`; all rendered package artifacts
then pass through the production schema, module, pipeline, registry, entry, contract, and seal APIs.

- Generated: `2026-07-19T03:32:53.092018+00:00`
- Command: `generate_fixture.py --output /home/reid/1cfe/teax/packages/teax-simkit/simkit/tests/evaluation/fixtures/f1_arithmetic/package_live --package-name f1_arithmetic_constraints --overwrite`
- Package name: `f1_arithmetic_constraints`
- sysml-codegen SHA: `512786c7dfab44fba7a0185d09e845b7494c702d`
- agentic-mbse SHA: `4ed2a0728ea49298666415cd389d9a6173a81a3e`
- Producer SHA-256: `e9b2954a15754e2dbebc45b2942ad8d63252849d87349c657376032da37f0677`
- uv version: `uv 0.10.0`
- Lockfile SHA-256: `b457136b857974c655094b86496dc88809b2dc405146340aa5f02ebb8a284c05`
- Python: `CPython 3.12.11`
- ABI/cache tag: `cpython-312`
- Platform: `linux-x86_64`
- sysml-codegen distribution: `0.1.0`
- agentic-mbse distribution: `0.1.0`
- Jinja2: `3.1.6`
- Pydantic: `2.12.5`
- PyYAML: `6.0.3`
- Environment fingerprint: `093675c53ec44ebcfd26d68dd072d5a86d9fc8bfdd1af1956da4359fe804e5ba`
- Graph constraint order: `f1_division_check, f2_power_check, f3_nested_check`
- YAML module order: `entry_fusion, f1_division_check, f2_power_check, f3_nested_check, constraint_report_aggregator, exit_point`
- TEAx topological order: `entry_fusion, f1_division_check, f2_power_check, f3_nested_check, constraint_report_aggregator, exit_point`
- Executable fingerprint: `32637566af1231ec32392c2095ef7b09a678375fad6c46ba21ee5401a11de54e`

## Resolved distributions

  - Jinja2==3.1.6
  - MarkupSafe==3.0.3
  - PyMuPDF==1.26.7
  - PyYAML==6.0.3
  - agentic-mbse==0.1.0
  - annotated-types==0.7.0
  - beautifulsoup4==4.15.0
  - click==8.3.1
  - img2table==2.0.0
  - numpy==2.5.1
  - opencv-contrib-python==5.0.0.93
  - pydantic==2.12.5
  - pydantic_core==2.41.5
  - pymupdf4llm==0.2.9
  - pypdfium2==5.11.0
  - python-dotenv==1.2.1
  - soupsieve==2.8.4
  - syside==0.8.4
  - sysml-codegen==0.1.0
  - tabulate==0.9.0
  - typing-inspection==0.4.2
  - typing_extensions==4.15.0
  - xlsxwriter==3.2.9
