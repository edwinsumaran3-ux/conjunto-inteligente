# Multimodal interaction boundary

Touch, keyboard, voice, agent and API inputs must produce the same `UICommand`
shape. The frontend never treats speech transcription as authorization. The
server remains authoritative for identity, authorization, step-up and execution.

`TouchActionButton` and `ExpandableCarousel` are primitives, not a substitute
for a complete clinical UI. They enforce large touch targets and selection
feedback while preserving keyboard semantics.
