# hr

Status: NOT IMPLEMENTED IN THIS STAGE.

The module boundary exists to prevent accidental cross-domain coupling. Functional code must be added only after its requirements, invariants, dependencies and gates are satisfied.

Forbidden: placeholder endpoints, fake persistence, silent fallbacks, cross-module database writes that bypass application services.
