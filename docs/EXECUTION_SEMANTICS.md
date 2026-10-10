# Frozen execution semantics

This page records execution details that are easy to blur when summarizing the protocol in prose. It is derived from the retained source and frozen compute/provenance records; it does not change any selection, outcome, or statistic.

## Local continuation sampling

For each of the 631 eligible decision-time steps, the frozen pipeline requested eight local continuations from `gpt-5.6-terra` with reasoning effort `medium`. The code records `requested_temperature=0.7` and `requested_top_p=0.95`, but the frozen provider path did not expose those controls for this model; the retained compute authority records `effective_sampling=provider_default` and `provider_seed_parameter=unavailable`.

The provider request allowed up to 8192 output tokens so reasoning responses would not fail solely because of the transport cap. The **scientific local continuation window** was 256 decision tokens: visible assistant text was truncated locally to the first 256 tokens before semantic grouping, while structured tool actions were treated atomically. The deterministic sampling key `(instance_id, step_index, continuation_index, 20260829)` is recorded for provenance even though the provider had no explicit seed parameter.

## Intervention refinement

The practical refiner requested temperature `0.2`. The frozen generator rejected the temperature parameter as unsupported; the replay code records that rejection and retries the same frozen request without the unsupported parameter. The retained accepted retry path omits the rejected parameter and records provider-default sampling. Retained execution code implements both the rejected attempt and the accepted retry. Sampled frozen H2 binding records document rejection and provider-default fallback; complete independently authenticated provider-side coverage for every branch is not established by this release.

## Why this is documented here

The reviewer-facing zero-API reproduction does not reissue these model calls. It operates on the frozen decision-time and closed-loop execution records. These details are exposed so that the publication copy of the code and the protocol record describe the executed experiment rather than an idealized API signature.
