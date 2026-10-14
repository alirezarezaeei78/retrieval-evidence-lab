# Local evidence inspector

Audience: knowledge teams and developers. One job: find a passage, inspect its source span, export an evidence report. No generated answer interface.

Design: a quiet document workbench. Cool blue canvas #E9F0F8, navy #142B4C, teal #066F72, amber #AC6A07, ink #233244, white #FFFFFF. Georgia for the restrained product heading, Segoe UI/system sans for controls/body, Consolas/monospace for source lines and scores. No external font downloads or animation.

Desktop: compact header; left query/document controls; right evidence cards. Mobile: stacked controls then results. Signature: source-ID and line-range gutters aligned beside exact excerpts, with matched tokens and document fingerprints. These labels encode provenance rather than decorative statistics. A clearly visible note explains that lexical similarity is not proof of an answer.

The first design considered generic dashboard metrics; those were removed because the user's actual task is inspecting passages. Keep query, source, rejection/error explanation and export together. Keyboard focus, labelled form fields, live status, semantic headings and plain-text safe output are required.
