# URL Shortener Greenfield Scenario Context

Build the requested target through the governed workflow and only within the approved target workspace.

The human-approved requirement analysis is the authoritative source for product scope. It incorporates the original requirement and accepted clarification answers. Do not add capabilities that are not explicitly included in the approved requirement. Explicitly excluded features must remain out of scope.

The scenario profile provides governance, safety, path-policy, and deterministic validation context only. It must not introduce product functionality such as custom aliases, expiration, analytics, statistics, health endpoints, or any other behavior not explicitly requested and approved.

Scenario `allowed_paths` constrain controlled modifications inside the target repository. They do not apply to orchestration artifacts, which the platform stores separately under its managed artifact root.

Derive the implementation from the approved requirement and architecture. Do not:

* import modules from the control-plane application;
* configure a Git remote;
* embed credentials or secrets;
* commit generated database files;
* modify files outside the effective task allowlist;
* bypass clarification, approval, validation, or release gates.

Treat deterministic validators, path-policy enforcement, workspace isolation, and the ControlledEditor as the final enforcement boundaries.
