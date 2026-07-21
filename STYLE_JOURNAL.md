# STYLE_JOURNAL.md — Elsevier Journal Writing Style Guide

This file defines an **alternative** academic writing style for this project, modeled on:
**Khandakar et al., "A machine learning model for early detection of diabetic foot using
thermogram images," Computers in Biology and Medicine 137 (2021) 104838 (Elsevier).**

It is a **second, distinct style** from the advisor-thesis style in `CLAUDE.md`. The two are
not compatible and must not be mixed within one document. Choose one style per document.

- Use **`CLAUDE.md`** for the master's thesis proposal (Mahidol format, advisor Morakot's voice).
- Use **this file** when drafting a **journal-paper submission** in the Elsevier / IEEE empirical style,
  or when the user explicitly asks for the "Khandakar style" or "journal style".

The rules below are derived from the source paper by pattern only. Never copy its sentences,
its numbers, or its wording. Reproduce the *pattern*, populate it with this project's own content.

---

## PART A — STYLE ANALYSIS (patterns extracted from the source)

### A.1 Text

**Sentence length and rhythm.**
Sentences are medium-to-long and information-dense, frequently compound. A typical sentence
carries a claim plus its evidence in the same breath, often through a subordinate clause opening
with *Whilst*, *Since*, *As*, *While*, or *Although*. Short punchy sentences are reserved for
stating a single headline result.

**Paragraph structure.**
Paragraphs are compact, roughly 4 to 8 sentences. The pattern is topic sentence, then supporting
detail or method, then an interpretive claim or observation that closes the paragraph. There is
little of the thesis-style "roadmap" previewing. A new finding usually starts a new short paragraph
rather than being folded into a long flowing one.

**Voice.**
Mixed. First-person plural is used for authorial actions ("We have compared", "We report",
"We have utilized"). Impersonal passive and evidential constructions carry the results
("It can be seen that", "It was found that", "were reported", "is applied", "was used").
This blend is characteristic and should be preserved, unlike the thesis style which pushes
"we" everywhere.

**Connectives.**
*However*, *Moreover*, *Indeed*, *Interestingly*, *Rather*, *Whilst*, *In addition*,
*On the other hand*, *As before*. *Interestingly* and *Indeed* are used to flag a result the
reader would not expect.

**Hedging language.**
Liberal and explicit. *may*, *might*, *could*, *is explained by the fact that*,
*This can be understood easily as*, *it is natural to*, *is questionable as*,
*might not be able to generalize*. Novelty is claimed with *To the best of our knowledge*.

**Reporting numbers.**
- Metrics are reported as **percentages** with **mean ± SD to two decimals**, e.g. `92.51 ± 5.44`.
- Approximate headline figures use a tilde, e.g. `~95%`.
- p-values are given both as a threshold and an exact value in scientific notation,
  e.g. `P < 0.05 (p-value = 5.46 × 10⁻⁷)`.
- Physical quantities carry units, sometimes dual, e.g. `2.22 °C (4 °F)`.
- Inference time in milliseconds to three decimals, e.g. `5.252`.

**Structural conventions.**
- A one-line section preview near the end of the introduction: "Section II discusses the
  methodology, Section III presents the results and discussion, and Section IV presents the
  conclusions."
- Contributions given as a **bulleted list** introduced by "The major contributions of this
  paper are:".
- Colons, semicolons, "i.e.", and "e.g." are used **freely** in prose. (This is the opposite
  of `CLAUDE.md` and is the single clearest tell that separates the two styles.)

### A.2 Tables

- **Caption placed above the table**, phrased as a descriptive noun clause followed by a
  reading cue: "Performance metrics for the binary classification using ... The best-performing
  network is highlighted in bold."
- **Booktabs-style horizontal rules only, no vertical rules** in the published look.
- Metric columns: `Accuracy (%) | Precision (%) | Sensitivity (%) | F1-score (%) | Specificity (%) | Inference time (msec)`.
- Rows are **grouped by model**, and each model spans **per-class rows plus an Overall row**
  (in the source, DM / CG / Overall).
- Cell values are **percentage mean ± SD to two decimals**.
- The **best-performing model's block is set in bold**.
- Statistical tables report the test name, the test statistic, and the p-value in scientific
  notation in dedicated columns.

### A.3 Figures

- **ROC curves** plotted as Sensitivity (True Positive Rate) versus 1 − Specificity
  (False Positive Rate), one **distinctly colored line per model**, legend naming each model.
- **Multi-panel figures labeled (A) and (B)** for before/after or method-1/method-2 comparisons,
  e.g. a correlation heatmap before and after feature reduction.
- **Feature-importance shown as horizontal bar charts**, ranked, one panel per ranking method.
- **Trade-off scatter plots** (e.g. F1-score versus inference time) that **encode a second
  categorical variable through marker shape** (square = deployable, diamond = not), explained by
  a "Note:" line in the caption.
- Color: saturated, categorical, one hue per series for line plots. A **jet / temperature
  colormap** (blue → green → yellow → red) for any intensity map.
- Caption pattern: state what is plotted, then, when markers or panels need decoding, add a
  short "Note:" clause on how to read them.

---

## PART B — WRITING RULES (apply these when drafting in this style)

1. **Blend voice.** Use "we" for what the authors did, impersonal passive and "It can be seen
   that / It was found that" for what the data show. Do not force "we" onto every result.

2. **One claim per short paragraph.** Open with the finding, give the evidence or mechanism,
   close with an interpretation. Keep paragraphs to 4 to 8 dense sentences.

3. **Report metrics as percentages, mean ± SD, two decimals.** Convert probabilities to
   percentages in this style (0.9803 ± 0.0080 becomes 98.03 ± 0.80 %). Keep the underlying value
   identical, only reformat.

4. **Give p-values twice.** Threshold plus exact value in scientific notation.

5. **Use colons and semicolons freely** to stack clauses, and "i.e." / "e.g." for asides.
   This is deliberately opposite to `CLAUDE.md`.

6. **Explain the unexpected with a hedge.** When a result surprises, flag it with *Interestingly*
   or *Indeed*, then explain it with *This can be understood easily as* or *is explained by the
   fact that*, and hedge the generalization with *may* or *might*.

7. **Claim novelty once** with *To the best of our knowledge*, placed just before the
   contribution or the first-of-its-kind statement.

8. **List contributions as bullets** in the introduction, and summarize "interesting
   observations" as bullets in the discussion.

9. **Tables:** caption above, descriptive plus reading cue, best block in bold, values as
   percentage mean ± SD, group rows by model with per-class and Overall rows.

10. **Figures:** ROC as Sensitivity vs 1 − Specificity with one hue per model; label multi-panel
    figures (A)/(B); encode a second variable by marker shape and decode it in a "Note:" caption.

11. **Preview sections in one line**, not a paragraph, at the end of the introduction.

---

## PART C — WHAT NOT TO DO

- Do not copy any sentence, phrase, or number from the source paper. Pattern only.
- Do not mix this style with the advisor thesis style in one document.
- Do not push everything into "we"; the impersonal passive is part of this voice.
- Do not report metrics as bare probabilities here; use percentage mean ± SD.
- Do not write long roadmap paragraphs; this style previews in a single sentence.
- Do not drop the "Note:" decoding line when a figure uses marker shape or panel labels.

---

## Quick contrast with `CLAUDE.md` (advisor thesis style)

| Dimension | `CLAUDE.md` (thesis) | This file (journal) |
|---|---|---|
| Colons / semicolons in prose | Forbidden | Used freely |
| Voice | "we" throughout | "we" + impersonal passive blend |
| Metric format | probability with CI, e.g. 0.9803 | percentage ± SD, e.g. 98.03 ± 0.80 % |
| Section opening | roadmap paragraph | one-line preview |
| RQ answer box | mandatory "Answer to RQX:" | not used; findings summarized as bullets |
| Paragraph length | 5 to 10 flowing sentences | 4 to 8 dense sentences |
| "Note that" flag | thesis hedging phrase | "Interestingly" / "Indeed" + explicit hedge |
