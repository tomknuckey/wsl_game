---
applyTo: "app.py"
---

# Streamlit App Guidance

- The app currently reads generated CSV reports from `data/output/actual/` and presents results; it is not the scoring pipeline or a writable participant workflow.
- Keep calculations that affect official scores in the pipeline and shared utility functions. The app may format data for display, but should not create a competing scoring implementation.
- Preserve the public results experience and existing report columns when changing the UI. Use stable IDs for application logic and human-readable names for display.
- Do not add authentication, persistence, or transfer writes unless the task explicitly asks for that work. For planned app and transfer work, read `docs/plan_2026_09_17.md` and `docs/webapp_plan.md` first.