# MGM intake: interpretation and semantic assessment

## Read the sample in its stated context

The repository's sample README describes a saved generated run, not a hand-corrected expected answer. It instructs the reader to begin with Native `understanding`, then `elements["mgm:project"]`, and follow OP joins. `object_id` is the receiving entity; `element_id` is the provider. Actual records reference Type records through `type_ids`; membership is not another OP join. Latent received the complete Native account without repository access. The stored outside scope is `archaeology`, while the original files precede publication normalization. [S02](evidence/source-index.md#s02)

Run `10c99044b7ca45f8944349b8b23dd21b` began against MGM source revision `5906ded0cd80177046340df41a822801501a0bcd`. Native reused a prior source-inspection map and checked the current checkout/guides. The README explicitly excludes a fresh exhaustive source audit and runtime validation. Execution-history records needed to reconstruct all earlier influences are absent. Those qualifications materially affect interpretation.

## Measured shape

| Measurement | Native | Latent |
| --- | ---: | ---: |
| Actual Elements | 58 | 72 |
| Type records | 47 | 47 |
| Total Element-table records | 105 | 119 |
| OP joins | 101 | 204 |
| Hard-dependency joins | 53 | 64 |
| Property joins | 15 | 66 |
| Supportive joins | 33 | 74 |
| Original file bytes | 191,818 | 522,668 |
| Distinct SVG strings across 47 Types | 4 | 4 |

Both files match their manifest SHA-256 hashes. All recorded Type references, explicit namespace prefixes, and OP endpoints resolved within their respective files in the performed checks. This establishes referential completeness of those fields, not correctness of their meanings. [measurements](evidence/measurements.json)

Latent retains all 105 Native record IDs, leaves all 47 Type records byte-equivalent as parsed records, revises all 58 actual records, and adds 14 actuals. All 101 Native join IDs recur, but only 100 retain the same receiver/provider/role/purpose tuple. The remaining changes include 104 Latent tuple keys not present in Native. ID overlap and semantic agreement must not be conflated.

## What the sample does well

The Defining Element is a representative composite, `mgm:project`, classified as `code.coordinator.gateway`, rather than a source file or executable entry point. Its EF describes coordinating gateways into usable forwarding paths as connectivity changes. `mgm:users` and `mgm:operators` receive that result for distinct purposes. This is a good artifact-level starting point.

Several subsystems are recognizable by their role in the account: connectivity observation, gateway choice, routing, mesh identity, management access, configuration, and operator guidance. Actual records remain distinct when Types are shared. Language/medium properties are attached locally: shell to particular provisioning/service Elements, C11 to particular executable Elements, and JavaScript to the interface. That local placement is preferable to declaring every descendant of `code` to have every language in the repository. [S02](evidence/source-index.md#s02)

The sample's freeform account and Mermaid diagram provide useful orientation. The outside pass identifies substantive questions about forwarding acceptance, peer trust, observation validity, convergence, and service progress. These should be retained as review knowledge even though their current structural placement is wrong for the requested model.

## Contamination is already inside Native

Every one of the 58 actual records in `native.json` has a provenance entry identifying a latent perspective. For example, `elements["mgm:project"].entity_json_obj.provenance` describes independent assessment of the supplied Native account, while its description contains `assessment_status` and run-level qualifications. `mgm:dnsresponders` likewise contains latent-assessment prose within its Native actual description. [measurements](evidence/measurements.json)

This is not proof that the current viewer selected the wrong source. The viewer preferentially uses Native for the actual's main presentation; the Native record itself already carries the interpretation. Nor does it prove an unseen prompt or a specific mutation bug. Prior-map reuse, previous analysis, and transport history cannot be disentangled from the supplied files alone.

The repair is concrete: preserve original observations; give each structural assertion its source evidence and generating activity; retain input-reuse lineage; place assessment conclusions and coverage limits in their own activity/layer records; and stop treating `scope == native` as synonymous with independently observed artifact truth. A new fresh intake can then be evaluated without silently cleaning historical evidence first.

## Initial resolution is inconsistent

The issue is not that 58 actuals exceed an arbitrary quota. Some are meaningful coarse components. Others carry implementation-resolution material inside the EF itself.

| Record | Recorded issue | Proposed coarse representation |
| --- | --- | --- |
| `mgm:originators` | EF names adapter behavior, EWMA thresholds, millisecond values, and rediscovery sample counts | Describe interpreting mesh-peer observations to update usable peer participation; keep thresholds and adapter evidence in an expansion |
| `mgm:sentryhandoff` | EF includes named initialization functions, callbacks, and a list of API paths | Describe sharing connectivity evidence with the running coordinator and its consumers; retain source-level handoff details as evidence |
| `mgm:ipgen` | EF combines hash selection, host-window mechanics, ARP retries, and mnemonic output | Describe deriving and provisioning repeatable mesh identity from supplied inputs; expose collision/probe details when relevant |
| `mgm:hosttests` | EF inventories six C executables and individual suites | Describe checking selected host-level behavior; keep suite inventory and measured coverage in test-analysis knowledge |
| `mgm:prototype` | Gateway-coordinator Type is paired with an EF about helping maintainers reconstruct earlier approaches | Separate what the historical artifact was from its current receiving-purpose role as reference material; do not redefine the universal coordinator EF to mean documentation |
| `mgm:securitylimit` | An actual operational boundary is mixed with assessment language | Preserve the reported peer-acceptance boundary where supported, and separate risk interpretation and proposed remedies |

These are proposed repairs to the recorded abstraction, not newly verified statements about the MGM source. Each replacement must be checked against the retained evidence and the receiver's purpose. A code function is evidence for a capability, not automatically the capability's Type.

## The outside result should be knowledge, not another artifact inventory

The 14 additional actual IDs are `mgm:latent:assessment`, `convergence`, `forwarding`, `identity`, `installation`, `management`, `observation`, `peeravailability`, `probevalidity`, `progress`, `protocol`, `selection`, `serviceacceptance`, and `trust` under that prefix. They are predominantly proposed specifications or cross-cutting contracts, with assessment priorities, acceptance scenarios, and evidence limits.

Keep their useful content as findings targeted to actuals, Types, joins, or regions. A finding that a contract is absent from the supplied representation should say precisely that; it must not become proof the implementation lacks the behavior. A proposed forwarding contract must not appear among current project components merely because the analyst can describe it well.

There is also a useful local role correction. Join `join:1167cd6b1b257607298cbf479a0c57b52186a01c5cec002b641d3724ad4ca06d` links `mgm:dictionary` to receiver `mgm:names`. Latent changes supportive to hard dependency and explains that vocabulary is necessary for this specific naming purpose, even though naming remains supportive to gateway coordination. That is sound **relationship-level reasoning** to preserve as a proposed correction, not a reason to promote the entire Latent graph as structural truth. The actual content and necessity of the embedded vocabulary still require its source evidence.

## Rubric outcome for this sample

The representation has a useful functional center, explicit exterior receivers, stable actual identity, reusable Type descriptions, and navigable relations. It is weaker in consistent coarseness, separation of observation from analysis, Type-to-actual EF alignment, and presentation of proposed knowledge. Referential completeness is comparatively strong; semantic purity and a reusable compact initial shape are not established.

For the next evaluation, use the revised intake on a fresh source snapshot and retain the raw answer, rendered assignment, source manifest, reuse record, and first published foundation separately. Compare the resulting orientation against this sample without treating a smaller count as inherently better. Ask an agent to identify the artifact's result, principal receivers, requirements, boundaries, and one local relationship without reading implementation code. Its ability to do so is the relevant first-use behavior.
