## Problem

Documentation is not maintained by developers and stays older than the code. Newcomers cannot tell that the docs are lying. Wrong documentation costs newcomers time and seniors time: newcomers believe it, and seniors explain how the system actually works. Worse, a newcomer who trusts a false statement builds on it, and the wrong work ships. An LLM generates text, but it cannot check whether that text is true.

## Input / Output

### Input

**The unit.** One repository — a service, worker, or library. The system assumes
one repository contains one service. A repository holding several services, or a
service split across repositories, is out of scope for v1.

**The context.** All other repositories belonging to the same system. The run may
read them, but produces no output for them. Context is what makes cross-service
fields possible: a service cannot know who it talks to by looking only at itself.

**Guaranteed present.** Source code of the unit.
**Optional.** Architecture decision records, database schema definitions.

### Output, level 1 — one object per unit

| Field | Type | Required | Producer |
|---|---|---|---|
| `service_name` | string | required | parser — repository name |
| `goal` | string | required | **model** |
| `evidence` | list of (path, symbol, lines, content_hash) | required | **model** names path and symbol; parser resolves `lines`; checker computes `content_hash` |
| `schema` | list of data models | required | parser — AST |
| `linked_doc` | list of service names | required | parser — imports and calls resolved against the context |
| `source_id` | string | required | parser — path and commit the claims were read from |
| `last_change` | date | required | parser — date of the last commit touching the unit |
| `last_author` | string | required | parser — author of that commit |
| `generated_at` | date | required | pipeline — clock at run time |
| `diagram` | mermaid source | optional | derived — rendered from `linked_doc` |

`goal` is the only prose the model writes. `evidence` is the model's claim about where in
the source it read that prose: it names a file and a symbol, the parser resolves that symbol
to a line range, and the checker hashes the region so the claim can be re-checked later —
see [Measurement](#measurement). Addressing by symbol rather than by line number is what
lets the citation survive edits above it. Every other field is extracted or derived, and
therefore cannot be fabricated.

### Output, level 2 — one object per system

| Field | Type | Required | Producer |
|---|---|---|---|
| `services` | list of level-1 objects | required | aggregation |
| `dependencies` | list of (caller, callee) pairs | required | derived — from every unit's `linked_doc` |
| `diagram` | mermaid source | required | derived — rendered from `dependencies` |
| `generated_at` | date | required | pipeline |

Level 2 is built from the level-1 objects, not from source code. No model is
involved, so nothing here can be invented.

### Stage 2 — rendering

| | |
|---|---|
| Input | a level-1 or level-2 object, and the unit's working tree at a render commit |
| Output | a page in a documentation site |
| Producer | template plus include resolution — deterministic given both inputs |

The page does not copy the code it describes. Every region named in `evidence` is
**transcluded**: the page carries a directive, and the site generator pulls the source in
at build time. A copy drifts away from its original; an include cannot, because there is
only one copy of the text. The reader sees the prose and a window onto the code it was
read from, side by side.

This is why the output is a site rather than a loose `.md` file. Plain markdown has no
include mechanism, and a git host renders a permalink inside a markdown file as a link,
not as a window onto the code. The generator has to resolve includes itself. Four do, and
any of them satisfies this spec:

| Generator | Directive |
|---|---|
| Sphinx | `.. literalinclude:: file.py` with `:pyobject: Timer.start` |
| MkDocs — `pymdownx.snippets` | `--8<-- "file.py:func"` |
| mdBook | `{{#include file.rs:component}}` with `// ANCHOR: component` in the source |
| Antora / AsciiDoc | `include::example$file.py[tag=func]` |

**Includes address code by symbol, never by a bare line range.** Every generator above
offers both forms, and the line-number form is the one that rots: three lines added above
a cited function, and the window shows the wrong code while still looking correct. A symbol
survives the shift. Where a symbol cannot be resolved, an anchor comment in the source is
the fallback; a line range stays the checker's internal record and is never the published
address.

An include that does not resolve at build time fails the build. A page that quietly lost
its evidence is worse than a page that never had any, because the prose still reads as
though it were sourced.

## Measurement

The generator is the easy half. This section defines what "the draft is true" means,
how it is decided, and what numbers have to hold before a change may ship.

### Two different claims

The output makes two kinds of claim, and they cannot be checked the same way.

| | Parser and derived fields | The model's field, `goal` |
|---|---|---|
| Claim | this value was read from the source | this sentence describes the unit |
| Check | exact comparison against the reference | judgement against the reference |
| Wrong means | the extractor is broken | the text says something false, empty, or invented |

Parser fields are checked by equality, so their correctness is a matter of fact.
Only `goal` needs a definition of truth, and everything below is mostly about it.

### Evidence makes fabrication decidable

A free sentence cannot be verified against a repository. A sentence with citations can.
So `goal` is never accepted alone: the model must also return `evidence` — the places
in the unit it read the claim from, at the commit named in `source_id`.

A checker then re-reads those places. Three outcomes:

- the cited region exists and contains what the claim says → the claim is **supported**
- the cited region exists but does not contain it → the claim is **unsupported**
- the cited region does not exist at that commit → the claim is **fabricated**

This is the whole reason the field list is split the way it is: `goal` is the only prose
the model writes, `evidence` is a claim about the source that the checker can re-read, and
every remaining field is extracted or derived and so has nothing to invent with.

### Drift: verified once is not verified forever

A claim is verified against one commit. The code then moves on. Without a further
mechanism the page shows prose that was true in the past beside a window that is true now,
with nothing to say the two no longer match.

So `evidence` carries a `content_hash` — the hash of the cited region as it stood at
`source_id`. The check runs again in CI against the current commit: resolve the symbol,
hash what it now contains, compare.

| Result | What the page shows |
|---|---|
| hash unchanged | verified at `<commit>`, code unchanged since |
| hash changed | verified at `<commit>`, **this code has changed since** — prose not re-verified |
| symbol gone | the evidence no longer exists: the block is withdrawn and the unit is queued for regeneration |

A region that changes marks itself. That is the property worth having — prose that has
fallen behind its code cannot sit on the page looking current.

What this does not do: a hash detects change, not falsehood. A rename, a reformat, or an
added log line changes the hash while the prose stays perfectly true. Drift is therefore a
**trigger for re-verification, not a verdict**. It says this needs looking at; only a rerun
of the measurement below says whether the sentence is now wrong. A system that treated
every hash change as a lie would cry wolf until readers stopped believing the marker.

### Precedence: code beats prose

Comments, docstrings, names, and README text are not evidence of behaviour. They are
evidence of what someone once intended. When a comment and the code it sits on disagree,
the code is right and the comment is a finding to report, not a source to quote.

A `goal` supported only by a comment that contradicts its own code counts as a
contradiction, not as a supported claim. This rule exists because the failure it prevents
is the most common one in the wild, and because it is the rule an LLM breaks first: stale
prose reads more like documentation than code does.

### The golden dataset

50 cases over the synthetic repository. One case is one unit at one pinned commit, plus a
reference answer written by hand.

A reference answer holds:

| Part | Content |
|---|---|
| Parser fields | the exact expected value of every extracted and derived field |
| Required facts | the statements a correct `goal` must contain |
| Forbidden facts | the statements a correct `goal` must not contain, with the reason |
| Verdict | for trap cases, which source the answer must follow and which it must reject |

Composition — chosen so that the traps cannot be averaged away by easy cases:

| Kind | Cases | What it tests |
|---|---|---|
| Plain | 28 | ordinary units, no conflicting signals |
| Traps | 12 | stale comment against live code; endpoint whose name lies; no type hints |
| Cross-service | 6 | `linked_doc` resolved against the context, not guessed from names |
| Insufficient information | 4 | the correct answer is to abstain, not to produce a plausible sentence |

Written by the author, by hand, as the domain expert — not generated by a model. A golden
set written by a model measures agreement with that model, which is not the thing being
measured. Cases are pinned to commits, so the repository cannot shift under a comparison.

### What counts as an error

| Class | Definition | Decided by |
|---|---|---|
| Fabrication | a statement whose evidence does not exist | checker, mechanically |
| Unsupported | evidence exists but does not carry the statement | judge |
| Contradiction | the statement disagrees with the code, including by trusting stale prose | judge |
| Omission | a required fact from the reference answer is missing | judge |
| Vagueness | true, but holds for any service — "handles requests", "manages data" | judge |
| False abstention | abstained on a case the reference answer calls answerable | comparison |
| Parser error | an extracted or derived field differs from the reference | comparison |

Fabrication and contradiction are the two that make a reader trust a lie. They are treated
as gates, not as scores to improve.

### Who judges

The author's labels are the reference. A model may be used as the judge for repeat runs,
but only after its agreement with those labels has been measured on the golden set and
reported as a number; below the agreement threshold the judge is not used and labelling
stays manual. The judge is given the cited source and one claim at a time, never the
generator's own explanation of itself — otherwise it grades the reasoning instead of
the source.

Agreement is re-measured whenever the judge's model or prompt changes. An unmeasured judge
is not a measurement.

### Metrics

| Metric | Definition | Target |
|---|---|---|
| Fabrication rate | share of cases with at least one fabricated statement | 0 — gate |
| Contradiction rate | same, for contradictions | 0 — gate |
| Schema validity | share of model responses that parse and validate | 100% — gate |
| Include resolution | share of `evidence` includes that resolve at build time | 100% — gate |
| Field accuracy | per field, share of cases matching the reference exactly | per-field floor |
| Required-fact recall | share of required facts present in `goal` | threshold |
| Vagueness rate | share of `goal` values judged vague | threshold |
| Abstention correctness | share of the 4 abstain cases answered by abstaining, and of the other 46 not | threshold |
| Judge agreement | agreement between judge and author labels on the golden set | threshold |
| Stability | over N repeats of the same case, share of cases whose verdict never changes | threshold |
| Stale-block rate | share of published blocks whose cited region changed since verification | reported, with a ceiling |
| Cost | USD per 1000 files, measured not estimated | reported, with a ceiling |
| Latency | p50 and p95 per unit | reported, with a ceiling |

Stability is measured because the generator is not deterministic. A number from a single
pass over 50 cases is not a measurement of the system, only of one sample of it; every
reported figure comes from N repeats, with N recorded next to it.

The four gates are absolute: a run that fails any of them fails, whatever the other
numbers say. The remaining thresholds are set before the first baseline run and are not
tuned to the result afterwards. Changing a threshold requires a written reason recorded
next to the number it replaced.

### Regression

Any change to a prompt, a model, the parser, or the judge triggers a full eval run before
it can ship. Each run appends one row — date, commit, model, judge, N, every metric above
— to a results table kept in the repository, so a regression is visible as a row rather
than remembered as a feeling. A run that fails a gate is committed too; hiding failed runs
would make the table useless as a history.

### Not measured

The page's layout and the template's wording, because the template states nothing of its
own — with one exception. The drift marker is a claim, and it is settled by hash comparison
rather than judged, so it falls under the gates above and not here. Prose style. The
context repositories, which are read but never described. Anything about repositories that
do not follow the one-repository-one-service assumption — those are out of scope for v1,
and no number here speaks for them.
