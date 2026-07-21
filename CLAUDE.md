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
- The `**Answer to RQX:**` label is fixed, but the sentence after it is not a template. Vary its
  construction across RQs so the boxes do not read as a filled-in form. One RQ may lead with the
  winning model, another with the size of the gap, another with the mechanism. Do not reuse the
  same "X achieves the highest Y, demonstrating the most balanced Z" frame every time.

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

The following is a **palette to rotate through**, not a set of stamps. Reusing "We however
acknowledge that..." at the head of every limitation is itself an AI-tell. Pick a different entry
each time, and when none fits, write the limitation as a plain sentence with no lead-in phrase.

- "We however acknowledge that..."
- "We note that..."
- "Note that... does not necessarily imply..."
- "For the sake of completeness,..."
- "This is expected given... and is reserved for future work."
- "It is acknowledged that..."

Never hide or soften a limitation — state it directly, then explain why the study is still valid.

---

## 9. Transition Language

Transitions exist to mark a genuine turn in the argument, not to decorate the start of every
paragraph. The default is **no opening connective** — let the topic sentence carry the logic. Add
a connective only when the relationship to the previous sentence would otherwise be unclear.

**Available connectives, grouped by the relationship they signal:**
- Hence, Thus, Therefore (logical consequence)
- However, In contrast, On the other hand (counterpoint)
- In addition, Moreover, Furthermore (adding support)
- For example, For instance, To illustrate (before examples)
- More specifically, In particular (before detail)
- In practice, (theory versus application)

**Hard limits, because overuse is the clearest AI-tell in this file:**
- Never open two consecutive paragraphs with a connective.
- Use "Moreover", "Furthermore", and "Additionally" at most once each per chapter. They stack
  into a robotic cadence. Prefer starting the sentence with its actual subject.
- Do not chain "Firstly / Secondly / Thirdly" mechanically. If the order matters, number a list.
  If it does not, drop the markers.

**Linking results to implications** — vary the wording, do not stamp the same phrase each time:
- "This suggests that..."
- "This is consistent with..."
- "One explanation is that..."
- "A likely cause is..."

Avoid the empty booster "These results demonstrate the effectiveness of...". State what the
result shows in concrete terms instead, such as which metric moved and by how much.

---

## 10. Table and Figure Conventions

### 10.1 Referencing and lead-in variation

- Reference every table and figure inline **before** it appears, so the reader meets the pointer
  before the float.
- **Vary the lead-in.** Opening every reference with "As shown in Table X" or "Figure X
  illustrates" is a template tell, in the same family as the connective overuse in §9. Rotate
  among several constructions and do not reuse one more than a couple of times per chapter.

| Lead-in verb | Fits when |
|---|---|
| Table X reports / lists | raw per-item values |
| Table X compares / contrasts | two or more methods side by side |
| Table X breaks down | one result split by class or fold |
| Figure X plots / shows | a curve or distribution |
| Figure X overlays | heatmaps or CAM output on an image |

- Often the cleanest reference is a **trailing parenthetical**, letting the finding lead and the
  pointer follow, such as "ConvNeXt-Tiny attains the highest AUC-ROC (Table X)." Prefer this when
  the number is the point, and reserve the "Table X reports..." opening for when the table itself
  is the subject.

### 10.2 Caption writing

- Caption length is a **deliberate choice, not a fixed rule**. Two conventions are both valid.
  A **short label caption** such as "Image Segmentation" is acceptable, and is the norm for a demo
  or process figure whose body text already explains it fully. A **descriptive, self-contained
  caption** is the journal convention and is preferred when the figure must stand alone. Pick one
  convention and apply it consistently within the document. Do not expand a short caption merely
  because it is short.
- Add a **reading cue** whenever the figure or table carries something the reader must decode to
  read it correctly, such as "the best performer is in **bold**", "the expert bounding box is
  drawn in red", or which line is which model. This cue is worth adding even to an otherwise short
  caption. Omitting it is the real defect, not brevity. When a colon helps here, it is acceptable
  per §15.
- Keep captions factual. Do not use "comprehensive", "novel", or "powerful" in a caption. The
  caption describes, it does not sell.
- Caption goes **above** tables and **below** figures, following the Mahidol template default.

### 10.3 The interpretation paragraph, without AI-tell

- After every table and every non-trivial figure, write at least one paragraph that **interprets**
  the key result. Never let a float stand alone.
- **Lead with the finding, not the float.** Write "ConvNeXt-Tiny achieves the highest AUC-ROC at
  0.9803 (Table X)" rather than "As can be seen from Table X, it is evident that...". The reader
  wants the result first.
- **Banned openers**, because they are empty and machine-flavoured, namely "As can be seen from",
  "It is evident that", "It is clear that", "Table X clearly shows / demonstrates". Delete the
  opener and state the finding directly.
- **Do not narrate the whole table row by row.** The table already holds every value. The
  paragraph selects the two or three numbers that matter, gives the gap between them, and explains
  why. Follow the discussion pattern in §6.
- Cite specific cells, not vague trends. "A gap of 0.29 in specificity" beats "notably better
  performance".

### 10.4 Insertion mechanics (LaTeX)

- Every float carries a `\label{}`, and every `\ref{}` matches it. Labels follow the existing
  scheme, namely `tab:` for tables and `fig:` for figures.
- Comparison tables include a row or column for the **proposed method in bold**, and the overall
  best cell or block in bold so the eye finds it without reading prose.
- Keep numeric formatting **consistent within a table**, namely the same number of decimals in
  every cell of a column, and report dispersion the same way throughout a chapter, such as
  mean with standard deviation or a point estimate with a confidence interval, but not a mix.
- Use `\ref{}` for numbers, never a hardcoded "Table 3", so numbering survives reordering.

---

## 11. "Note that" Flags

Use **"Note that..."** to proactively address anything that might confuse or mislead the reader:

> "Note that velocity(Difference) = 0 does not necessarily imply that an iteration has delivered on all its commitments..."

Use this whenever a result, definition, or metric could be misread. Reserve it for genuine
misreading risks, at most once or twice per section. If "Note that" opens three sentences on one
page, the reader stops seeing it as a flag and it becomes verbal tic. When the caveat is minor,
fold it into the sentence instead of announcing it.

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

**Do not reflexively reach for "namely".** Replacing every colon with "namely" turns it into its own
tic, the same failure mode as the connective overuse in §9. It is one option, not the default. Try
the lighter fixes first, in this order:
- **Bare apposition** with a comma, when the list simply renames the preceding noun, as in
  "two steps, the E-step and the M-step" or "three categories, texture, shape, and geometric".
- **Fold the list into the sentence** as a direct object, as in "we compute the Contrast,
  Correlation, Energy, and Homogeneity of each orientation" rather than "four statistics, namely...".
- **"such as"** for a non-exhaustive example, or **"comprising" / "consisting of"** for a full one.

Reserve "namely" for the few cases where a formal lead-in genuinely aids clarity, and use it at most
a couple of times per chapter. If it appears more than that, restructure the extras.

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

## 16. Human Voice — Avoiding AI-Tell Phrasing

The rules above control *structure*. This section controls *voice*, so the prose reads as though a
researcher wrote it rather than a language model. AI-generated academic text has a recognizable
signature, namely uniform sentence length, reflexive connectives, inflated vocabulary, and empty
summary sentences. The goal is to remove that signature without losing the advisor's formal tone.

### 16.1 Vary sentence length deliberately

Human academic prose mixes short and long sentences. Machine prose defaults to a steady stream of
medium-to-long sentences of similar shape. After drafting a paragraph, read it aloud. If every
sentence runs 20 to 30 words, break one into a short declarative of 6 to 10 words. A short
sentence after two long ones lands a point. Do not make every sentence short either, as staccato
reads as a slide deck. The target is genuine variation, not a new uniform.

### 16.2 Do not open every sentence the same way

Vary the opening. Not every sentence should start with the subject, and not every paragraph should
start with a connective. Rotate among a subject opening, a short subordinate clause, a
prepositional phrase, and occasionally the result itself. What matters is that the pattern is not
predictable from one sentence to the next.

### 16.3 Cut inflated vocabulary and use the plain word

The following words are AI-tells when used as filler. Replace them with the plain equivalent, and
keep a domain term only when it is the genuine technical name.

| Avoid as filler | Use instead |
|---|---|
| utilize, leverage | use |
| in order to | to |
| a wide range of, a myriad of, various | name the actual items, or give the count |
| robust, powerful, seamless, cutting-edge | drop it, or state the concrete property |
| comprehensive, holistic | drop it, or say what is covered |
| plays a crucial / vital / pivotal role | say what it actually does |
| significant (when not statistical) | large, marked, or a number |
| delve into, explore in depth | examine, study |
| facilitate, enable (as filler) | the specific verb |

Note that some of these are legitimate technical terms in this project. "Image enhancement" and
"contrast enhancement" are the real names of the preprocessing step, so "enhance" is correct
there. "Statistically significant" is correct when reporting a test. The rule targets the *filler*
use, not the technical use. Before deleting, check which sense is meant.

### 16.4 Delete empty scaffolding sentences

Cut sentences that announce rather than inform. "It is important to note that", "It is worth
noting that", and "It should be emphasized that" can almost always be deleted, keeping only what
follows. Cut summary sentences that restate the paragraph without adding anything, such as "In
summary, these findings highlight the importance of...". End a paragraph on its last real point,
not on a restatement.

### 16.5 Avoid the machine constructions

- **"Not only X but also Y"** reads as generated. Rewrite as two clauses or one plain list.
- **Reflexive rule-of-three.** Listing exactly three adjectives or three examples every time is a
  pattern. Sometimes the honest answer is one example or two. Match the count to the content.
- **Stacked hedges** such as "may potentially suggest that it could possibly" — keep one hedge.
- **Elegant variation.** Do not swap "model", "framework", "approach", "system", and "method" to
  avoid repetition. Pick one term for one concept and repeat it. Consistent terminology is more
  scholarly than synonym rotation, and synonym rotation is itself an AI-tell.

### 16.6 Prefer the concrete over the abstract

When a sentence reaches for "various factors", "several aspects", or "a number of challenges",
stop and name them. Concrete nouns and specific numbers are the strongest signal of a human author
who actually knows the material. "Three preprocessing steps, namely cropping, resizing, and
contrast enhancement" beats "a series of preprocessing steps".

### 16.7 The read-aloud check

Before considering any passage finished, read it aloud once. Flag anything that a person would not
say in a research talk, such as a triple connective, a filler adjective, or a sentence that
restates the previous one. This single pass removes most of the remaining machine texture. This
check is consistent with the "review after edit" habit already followed in this project.

### 16.8 Do not bold or emphasize words mid-prose

Formal thesis prose does not bold a phrase in the middle of a sentence for emphasis. Reserve
`\textbf{}` for structural labels, namely itemize lead terms such as `\textbf{Name:}`, table
headers, sub-figure labels such as `\textbf{(A)}`, and the bolded paper name that leads each
related-work paragraph. Do not bold a phrase in flowing prose to draw attention to it, such as
`\textbf{foot image level}` or an organization name. Bolding both sides of a contrast cancels the
emphasis, and bolding one phrase per paragraph reads as textbook or AI styling rather than
scholarly prose. Let the sentence and its topic sentence carry the weight. If a key term genuinely
needs marking on first definition, use `\emph{}` once and sparingly, never `\textbf{}`.

---

## 17. What NOT to Do

- Do not use pure passive voice where "we" fits
- Do not present equations without a motivating example first
- Do not leave RQ answers implicit — always write the Answer box
- Do not write a result table without an interpretation paragraph after it
- Do not omit threats to validity in empirical chapters
- Do not use bullets in flowing argument sections (reserve for lists, criteria, features)
- Do not start a chapter section without previewing what it covers
- Do not use `:` or `;` in flowing prose — restructure with conjunctions instead
- Do not use `---` or `--` as parenthetical dashes in prose — rewrite as a relative clause or split sentence
- Do not open consecutive paragraphs with a connective, and do not reuse "Moreover / Furthermore / Additionally" more than once per chapter
- Do not write every sentence at the same medium length — vary short and long deliberately (§16.1)
- Do not use filler vocabulary such as "utilize", "leverage", "robust", "comprehensive", "a wide range of" when the plain word carries the meaning (§16.3)
- Do not keep empty scaffolding such as "It is important to note that" or restatement summaries (§16.4)
- Do not use "not only X but also Y", stacked hedges, or synonym rotation for the same concept (§16.5)
- Do not stamp the same fixed phrase into every RQ answer, limitation, or "Note that" flag — vary the wording (§5, §8, §11)
- Do not open every table/figure reference with "As shown in Table X" or "Figure X illustrates" — vary the lead-in (§10.1)
- Do not open an interpretation with "As can be seen", "It is evident that", or "clearly shows / demonstrates" — lead with the finding (§10.3)
- Do not omit a reading cue when a float needs decoding (bold best, colored box, which line is which), and do not narrate a table row by row — short captions are fine, missing cues and row-by-row narration are not (§10.2, §10.3)
- Do not bold or emphasize words mid-prose — reserve bold for structural labels, and let the sentence carry the emphasis (§16.8)
- Do not reflexively use "namely" to introduce every list — prefer bare apposition, folding the list into the sentence, or "such as"; use "namely" at most a couple of times per chapter (§15)

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
