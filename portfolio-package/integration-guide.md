# Importing into a separate portfolio

## Suggested mapping

| Portfolio field | Source |
| --- | --- |
| Project card title and summary | `project.json` |
| Hero image | `assets/cover.png` |
| Architecture section | `assets/architecture.png` |
| Product screenshot | `screenshots/investigation-console.png` |
| Long project page | `case-study.md` |
| Technology chips and metrics | `project.json` |

Copy the whole `portfolio-package` directory first. Rename assets only if the portfolio build
requires it, then update the paths in `project.json`.

## Recommended page order

1. Cover, title, and one-sentence summary
2. Problem and product screenshot
3. Architecture diagram
4. RAG and agent design decisions
5. Safety and approval boundary
6. Evaluation results with the synthetic-dataset disclosure
7. Limitations and next steps

The repository URL is set in `project.json`. The live-demo URL remains `null`; add it only
after a hosted deployment exists and has been checked from a clean browser.

Keep this disclosure near the metrics: “Results are from the included synthetic regression
benchmark and are not production accuracy.”
