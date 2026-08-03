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

## Key results

- The Greenfield scenario completed its governed workflow and reached release readiness.
- The Brownfield scenario exercised repository-aware analysis and controlled changes.
- The Ambiguous scenario demonstrated clarification pause and durable resume behavior.
- The final verification run completed with 259 tests passed and 3 skipped, with Ruff and
  whitespace validation passing.

## Screenshot and video evidence

- [Screenshot evidence for all three scenarios](three-scenario-screenshot-evidence.pdf)
- [Ambiguous Scenario 3 video demonstration](https://drive.google.com/drive/folders/1OFURyh3AvgU3c7pBqPkgEXVUiKJN1zAz?usp=sharing)

Due to the evaluation time constraints, only the Ambiguous scenario was recorded as a video. The
PDF contains screenshot evidence for Greenfield, Brownfield, and Ambiguous.

## Detailed references

- [API and Schema Contracts](api-and-schema-contracts.md)
- [Architecture Overview](architecture-overview.md)
- [Final Engineering Summary](final-engineering-summary.md)
- [Interactive Benchmark Reliability](interactive-benchmark-reliability.md)
- [Orchestration Model](orchestration-model.md)
- [Risks, Trade-offs, and Limitations](risks-tradeoffs-limitations.md)
- [Testing and Validation](testing-and-validation.md)
