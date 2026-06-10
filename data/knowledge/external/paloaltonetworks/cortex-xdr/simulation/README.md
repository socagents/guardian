# Cortex XDR — simulation recipes (placeholder)

This directory will host future R3.C-style data-source YAMLs that describe
how Phantom's xlog should generate XDR-shaped records for operator-driven
simulation workflows.

As of v0.14.0 this directory is intentionally empty — the Cortex XDR
bundled data source already ships in `bundles/spark/data-sources/`
for the marketplace, and the simulation YAMLs there are sufficient.
This dir exists so the layout matches the broader vendor knowledge tree
(`data/knowledge/external/<vendor>/<product>/{action,simulation}/`).

Future work: when we add custom XDR-flavored simulation scenarios beyond
what the marketplace provides, the YAMLs land here.
