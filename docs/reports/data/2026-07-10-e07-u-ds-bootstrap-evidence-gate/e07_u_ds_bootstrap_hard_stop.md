# AAAI-E07 U-ds Bootstrap Evidence Gate

_Read-only evidence audit of the frozen four-domain Gate-0 sample, 2026-07-10_

---

## 🚫 Outcome

`AAAI-E07` reached a **HARD STOP** and no bootstrap was run. The formal Gate-0 archive retains only four dataset aggregates and coherence-quartile aggregates. It does not retain per-transition utilities, realized negative IDs, transition IDs, or user-cluster identifiers. A user-clustered bootstrap therefore cannot be performed without regenerating transitions or negatives, which is outside the authorized scope.

The executed bootstrap replicate count is `0`. This records a blocked computation; it does not imply zero uncertainty.

## 📊 Archived point estimates

These are transcribed aggregate observations, not bootstrap rows.

| Dataset | Reported sampled transitions | `U_ds` popularity | `U_ds` uniform |
| --- | ---: | ---: | ---: |
| ML1M | 4,000 | 0.75353875 | 0.79852625 |
| Beauty | 4,000 | 0.71242750 | 0.71720375 |
| ATG | 4,000 | 0.68826250 | 0.69201250 |
| Steam | 4,000 | 0.56956625 | 0.56507875 |

The observed descending point order is `ML1M > Beauty > ATG > Steam`. A 95% interval and full-order retention probability are not estimable from the archived aggregates.

## 🔎 Evidence audit

| Source | Finding | Eligibility |
| --- | --- | --- |
| Formal Gate-0 report | Four dataset aggregates plus sixteen quartile aggregates | Ineligible: no transition or user identity |
| Formal summary CSV | One aggregate row per dataset | Ineligible: aggregate only |
| Formal coherence CSV | One aggregate row per dataset-quartile | Ineligible: quartile means cannot restore within-user variation |
| Gate-0 generator | Per-transition arrays remain in memory and are not written | Confirms missing archive layer |
| l20 formal archive | 23 files; no qualifying per-transition artifact | Ineligible |
| Git history | Only ML1M and Steam FOLLOWUP-09 transition files found | Incomplete and different protocol |
| FOLLOWUP-09 | 19,328 ML1M rows and 127,292 Steam rows, four rows per user, no uniform utility | Ineligible as a substitute |

The local and l20 SHA-256 values of the four core sources match exactly. See `e07_evidence_gate.json` and `e07_evidence_inventory.csv` for hashes and exclusion reasons.

## 🧪 Definitions and interpretation boundary

Popularity negatives are 100 iid draws with replacement from the empirical train next-item distribution. Uniform negatives are 100 iid draws with replacement over the catalog item-ID range. Per-transition utility compares the true next item's cosine similarity against each negative, assigning `1` for a strict win and `0.5` for a tie.

The original generator used sampling seed `7`, but the realized transitions, negative IDs, and per-transition utilities were not archived. Re-running that generator would regenerate evidence and was not done.

Under exchangeability, `1/24` is only the descriptive combinatorial fraction associated with one specified order among `4!` equally likely label orders. It is not a confirmatory p-value, and no confirmatory inferential test was performed here.

## 🔒 Actions not taken

- No transition sample was regenerated
- No popularity or uniform negatives were regenerated
- No aggregate or quartile row was treated as a transition record
- No FOLLOWUP-09 record was substituted for the Gate-0 sample
- No training or model-seed run was launched
- No interval, order-retention probability, or training-seed variance was imputed

## 📝 Paper-safe wording

> In the single archived Gate-0 sampling observation, the observed `U_ds` point estimates order the four datasets as `ML1M > Beauty > ATG > Steam`. Because the frozen per-transition records and user-cluster identifiers were not archived, this run cannot estimate uncertainty or full-order retention. Under exchangeability, `1/24` is only a descriptive combinatorial calculation, not a confirmatory p-value.
