# RISK-05 preflight blocker after RISK-04 assets

The real RISK-04 banks are valid, but the train-only preflight cannot be
started from the currently available frozen proposal checkpoints.

Read-only inspection on l20 showed that the candidate Beauty and ML1M
proposal checkpoints expose `text_side_builder.item_embeddings` and related
legacy fields, but no `text_side_builder.p1` or equivalent `core_p1` vector.
The current `proposal_records.py` contract requires a finite v2 core-p1 vector
with length `item_count + 1` and binds its SHA-256 before producing
train-only `q_text/q_core` records. The old checkpoint is therefore not a
valid input to RISK-05; reinterpreting another tensor as p1 would change the
method and violate the frozen protocol.

Consequences:

- RISK-04 remains an asset-only PASS with `severe_gate=pending`.
- RISK-05 preregistration and RISK-06/07 pilot are not authorized.
- No RISK-08 marker can be emitted, so method-pass continuation and all new
  seed-100 GPU training remain blocked.
- GPU0 CLOSE-10 was not touched; GPU1 remains available.

Required next dated attempt: implement and audit the RISK-09 common proposal
adapter, run the approved isolated host/core seed-100 training that produces a
real v2 core-p1 artifact, then generate proposal records and the frozen
train-only preflight. No tensor substitution or copied published number is
allowed.
