# CLAUDE.md — Research Writing Style Guide

This file defines the academic writing style for this project.
The target style is modeled on the advisor's thesis:
**Morakot Choetkiertikul, "Developing analytics models for software project management,"
PhD thesis, University of Wollongong, 2018.**

The current work is a **master's thesis proposal** (LaTeX, Mahidol University format).
Apply this style guide whenever writing, editing, or extending any `.tex` file in this project.

---

## 1. Voice and Person

- Use **first-person plural** throughout: "we propose", "we collected", "we employ", "we observe", "we acknowledge"
- Avoid passive-only constructions where "we" fits naturally
- Use passive only when the actor is genuinely unknown or unimportant

**Examples:**
> "We propose a CNN-based DFU risk classification model..."
> "We collected plantar pressure footprint images from 300 diabetic patients..."
> "We observe that ConvNeXt-Tiny achieves the highest AUC-ROC across all five folds."

---

## 2. Chapter and Section Opening

- Open every chapter with a **paragraph that previews the structure** of that chapter, naming each section explicitly:

> "The first part of this chapter (Section X.X) presents... The second part (Section X.X) describes... The final section (Section X.X) summarizes..."

- This gives the reader a roadmap before diving into content.

---

## 3. Motivating Examples Before Formal Definitions

- Always **introduce a concrete, narrative example first**, then follow with the formal notation or equation
- Never open with a definition or equation cold

**Pattern:**
1. Motivating paragraph (what is the problem? why does it matter?)
2. Concrete example with real or hypothetical data
3. Formal definition / equation
4. Notation explanation ("where X is...", "Note that...")

**Example from advisor:**
> "Let tpred refer to the time at which a prediction is being made (e.g. the third day of a 17-day iteration). Given time tpred during an iteration, we would like to predict the amount of work delivered..."
> *[Then the formal Definition 1 follows]*

---

## 4. Formal Definitions

- Use the format: **Definition X (Name)** before introducing a key formula

> **Definition 1 (Velocity)** Velocity of a set of issues I is the sum of story points of all issues in I: ...

- Follow every equation with a "where" clause explaining each variable

---

## 5. Research Question Answer Boxes

- After presenting evaluation results for each RQ, **explicitly summarize the answer** in a distinct line:

> **Answer to RQ1:** ConvNeXt-Tiny achieves the highest mean AUC-ROC (0.8293) across all five folds, demonstrating the most balanced performance between sensitivity and specificity among the three backbones evaluated.

- This is mandatory after every RQ result subsection — do not leave the RQ implicitly answered.

---

## 6. Result Discussion Pattern

After reporting numbers, always explain **why** the result occurred, not just what it is.

**Pattern:**
1. State the finding with specific numbers
2. Identify the phenomenon or pattern
3. Explain the likely cause or mechanism
4. Acknowledge any limitations or alternative explanations

**Example:**
> "The near-zero specificity of ResNet50 (0.1533) is consistent with a model that predicts the majority class for almost all inputs. This behavior is attributable to the class imbalance in the INAOE dataset (CT:DM = 90:244) rather than an inherent architectural limitation."

---

## 7. Threats to Validity

- Every chapter with empirical results must include a **Threats to Validity** section
- Organize into four subsections:
  1. **Threats to construct validity** — are the measured variables the right ones?
  2. **Threats to conclusion validity** — are statistical methods sound?
  3. **Threats to internal validity** — data preprocessing, leakage, confounds
  4. **Threats to external validity** — generalizability beyond this dataset/setting

- Always end each threat with what was done to mitigate it, or acknowledge it openly if not mitigated.

---

## 8. Acknowledging Limitations Explicitly

Use these phrases to flag known limitations honestly:

- "We however acknowledge that..."
- "We note that..."
- "Note that... does not necessarily imply..."
- "For the sake of completeness,..."
- "This is expected given... and is reserved for future work."
- "It is acknowledged that..."

Never hide or soften a limitation — state it directly, then explain why the study is still valid.

---

## 9. Transition Language

**Between paragraphs / ideas:**
- Hence, Thus, Therefore (for logical consequence)
- However, In contrast, On the other hand (for counterpoint)
- In addition, Moreover, Furthermore (for adding support)
- For example, For instance, To illustrate (before examples)
- More specifically, In particular (before detail)
- In practice, (to contrast theory vs. application)

**Linking results to implications:**
- "This suggests that..."
- "This confirms our earlier hypothesis that..."
- "This result is consistent with..."
- "These results demonstrate the effectiveness of..."

---

## 10. Table and Figure Conventions

- Reference every table/figure inline **before** it appears: "as shown in Table X", "Figure X illustrates"
- Caption format: short description first, then what to look for (e.g., "the best performer is marked with *")
- For comparison tables, always include a row/column for the proposed method in bold
- After every table, write at least one paragraph **interpreting** the key result — never let a table stand alone

---

## 11. "Note that" Flags

Use **"Note that..."** to proactively address anything that might confuse or mislead the reader:

> "Note that velocity(Difference) = 0 does not necessarily imply that an iteration has delivered on all its commitments..."

Use this whenever a result, definition, or metric could be misread.

---

## 12. Paragraph Length and Style

- Paragraphs are typically **5–10 sentences** of flowing prose
- Avoid bullet-heavy sections in the main body text (bullets are for feature lists, inclusion criteria, etc.)
- Each paragraph has a clear topic sentence and ends with an implication or transition
- Technical details are embedded in prose, not isolated

---

## 13. Citation Style

- Follow Mahidol University thesis template (muthesis2021.cls): **name-year** `\cite{}` style
- Inline citations: "Author \& Author (Year)~\cite{key}" when the author is the subject
- Parenthetical: use `~\cite{key}` at the end of the sentence when the citation is supporting evidence
- Do not use numbered citations [1] — that is the advisor's institutional style, not ours

---

## 14. Related Work Structure

For each reviewed paper, cover these four points in order:
1. **Dataset** — what data was used
2. **Method** — what approach was proposed
3. **Results** — key performance numbers
4. **Limitations** — what the paper did not address (this sets up our gap)

End the Related Work section by explicitly stating how this study addresses the identified gaps.

---

## 15. Punctuation — Avoid Colons, Semicolons, and Em Dashes

The advisor explicitly prefers conjunctions and restructured sentences over punctuation shortcuts.

### Colons and semicolons
- **Avoid `:` and `;`** as connectors within prose sentences
- Replace with conjunctions or restructure the sentence entirely

| Instead of | Use |
|---|---|
| `three tools: SWME, IpTT, and VPT` | `three tools, namely SWME, IpTT, and VPT` |
| `two steps: the E-step and the M-step` | `two steps, the E-step and the M-step` |
| `high pressure; this causes tissue damage` | `high pressure, which causes tissue damage` |
| `It consists of X; regions of higher pressure...` | `It consists of X. Regions of higher pressure...` (split into two sentences) |

- Colons are **only acceptable** in: table/figure captions, itemize lead terms (`\textbf{Name:}`), and equation "where" clauses
- Semicolons are **only acceptable** in: itemize entries that list parallel items (e.g., table cells), never in flowing prose paragraphs

### Em dashes
- **Avoid `---` and `--` as parenthetical insertions** in prose
- Replace by restructuring the sentence, using a relative clause, or splitting into two sentences

| Instead of | Use |
|---|---|
| `background --- the platform area not covered by the foot ---` | `background, which refers to the platform area not covered by the foot,` |
| `three regions --- background, low-pressure, and high-pressure` | `three regions, namely the background, low-pressure, and high-pressure zones,` |
| `a critical property --- a 15-pixel margin corresponds to 6.7%` | `a critical property, as a 15-pixel margin corresponds to 6.7%` |

- Em dashes are **only acceptable** in: informal inline notes in figure/table captions, never in body prose

---

## 16. What NOT to Do

- Do not use pure passive voice where "we" fits
- Do not present equations without a motivating example first
- Do not leave RQ answers implicit — always write the Answer box
- Do not write a result table without an interpretation paragraph after it
- Do not omit threats to validity in empirical chapters
- Do not use bullets in flowing argument sections (reserve for lists, criteria, features)
- Do not start a chapter section without previewing what it covers
- Do not use `:` or `;` in flowing prose — restructure with conjunctions instead
- Do not use `---` or `--` as parenthetical dashes in prose — rewrite as a relative clause or split sentence

---

## Project Context

- **Title**: CNN-based DFU Risk Classification Using Plantar Pressure Footprint Images
- **Type**: Master's thesis proposal, Mahidol University
- **Language**: English (academic)
- **LaTeX template**: muthesis2021.cls
- **Main files**: `chapter1.tex`, `chapter2.tex`, `chapter3.tex`, `abstract.tex`
- **Key models**: EfficientNetB0, ResNet50, ConvNeXt-Tiny (proposed); GLCM+HOG+BPNN (baseline)
- **Key methods**: Transfer learning, 5-fold CV, Optuna, Grad-CAM, Grad-CAM++, Eigen-CAM
- **Dataset**: 300 diabetic patients, Buddhachinaraj Hospital, Phitsanulok, Thailand
