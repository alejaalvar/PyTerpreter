---
name: journal
description: Use when ending a coding session or finishing a feature implementation to record decisions, progress, and lessons learned.
---

At the end of every feature implementation or coding session, append a Markdown entry to `JOURNAL.md` in the project root. Create the file if it does not exist. Format the entry exactly as follows:

## [Date] - Feature: [Name]
- **Goal**: One sentence on what we tried to build.
- **Decisions**: Why we structured the code this way and what alternatives we skipped.
- **Done**: Bullet points of what is fully working.
- **Next Steps**: What to do immediately next.
- **Debt/TODOs**: Any shortcuts, hacks, or refactoring needed later.
- **Lessons**: Unexpected bugs encountered and how they were solved.

Use today's actual date. Infer the feature name from the work just completed.
