# Final Evidence Summary

This page provides a concise visual overview of the system and points reviewers to the detailed
engineering documentation when more depth is needed.

## Architecture diagram

![Agentic Software Engineering System architecture](images/system-architecture.jpg)

## Scenario sequence diagrams

### Greenfield

![Greenfield workflow sequence](images/greenfield-sequence.svg)

### Brownfield

![Brownfield workflow sequence](images/brownfield-sequence.svg)

### Ambiguous requirement

![Ambiguous requirement workflow sequence](images/ambiguous-sequence.svg)

## Scenario evidence

| Scenario | Selected workflow | Result | Evidence focus | Generated artifacts |
| --- | --- | --- | --- | --- |
| Greenfield | `WF-7989E1418EA9` | READY | Governed creation from requirements through release | [Review artifacts](../generated_artifacts/interactive-mode-evidences-for-3-scenarios/WF-7989E1418EA9/) |
| Brownfield | `WF-6D6C54D2DAD9` | READY | Repository analysis, governed source copy, analytics change, and validation | [Review artifacts](../generated_artifacts/interactive-mode-evidences-for-3-scenarios/WF-6D6C54D2DAD9/) |
| Ambiguous | `WF-A73E0C8C31C4` | READY after clarification | Human clarification interrupt, durable resume, governed change, and validation | [Review artifacts](../generated_artifacts/interactive-mode-evidences-for-3-scenarios/WF-A73E0C8C31C4/) |

Additional Brownfield workflow `WF-9D68C26C57A2` also reached READY. Ambiguous workflow
`WF-95C6190BCF43` remains at `WAITING_FOR_CLARIFICATION`; it demonstrates the human clarification
boundary and is not a failed workflow. See [Interactive Benchmark Reliability](interactive-benchmark-reliability.md)
for the complete five-record dataset and metric definitions.

## Verification baseline

| Verification | Result |
| --- | ---: |
| Platform test suite | 259 passed |
| Expected Windows symbolic-link skips | 3 |
| Ruff | Passed |
| `git diff --check` | Passed |

These results demonstrate the selected assignment scenarios and local prototype controls. The
candidate mapping is profile-based because exact provider and scripted-scenario identity are not
durably persisted, and the dataset is not statistically meaningful production reliability.

## Screenshot and video evidence

- [Screenshot evidence for all three scenarios](three-scenario-screenshot-evidence.pdf)
- [Ambiguous Scenario 3 video demonstration](https://drive.google.com/drive/folders/1OFURyh3AvgU3c7pBqPkgEXVUiKJN1zAz?usp=sharing)

Due to the evaluation time constraints, only the Ambiguous scenario was recorded as a video. The
PDF contains screenshot evidence for Greenfield, Brownfield, and Ambiguous.

## Detailed references

- [README setup and demonstration guide](../README.md#prerequisites-and-setup)
- [API and Schema Contracts](api-and-schema-contracts.md)
- [Architecture Overview](architecture-overview.md)
- [Final Engineering Summary](final-engineering-summary.md)
- [Interactive Benchmark Reliability](interactive-benchmark-reliability.md)
- [Orchestration Model](orchestration-model.md)
- [Risks, Trade-offs, and Limitations](risks-tradeoffs-limitations.md)
- [Testing and Validation](testing-and-validation.md)
