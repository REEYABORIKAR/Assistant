---
name: asd-ste100-advanced
description: Advanced ASD-STE100 rewriting with detailed rules — short sentences, active voice, one meaning per word, warnings before steps. Use when writing or revising documentation, procedures, README files, or any explanation that must stay unambiguous. Triggers: STE rewrite, simplify technical writing, plain language.
---

# ASD-STE100 Simplified Technical English (Advanced)

ASD-STE100 is a controlled-language standard from the aerospace industry. It exists because a maintenance manual read at 3 a.m. by a second-language speaker must have exactly one possible reading. The same constraint makes it excellent for study notes and developer documentation.

## Before you rewrite

Ask which of the three text types you have. The rules differ.

| Type | Purpose | Sentence limit |
|---|---|---|
| **Procedural** | Tell the reader to do something | 20 words |
| **Descriptive** | Explain how something works | 25 words |
| **Safety** | Warn before harm | 20 words |

A single document usually mixes all three. Classify each block, not the whole file.

## Never touch these

Rewriting these breaks something. They are outside the rules:

- **Code.** Identifiers, keywords, commands, file paths, output. Never rename a variable "for clarity" — it breaks every call site and the reader's ability to match the text to their own file.
- **Direct quotations** and cited text.
- **Proper nouns**, product names, and Technical Names (`hash table`, `mutex`, `race condition`). STE explicitly permits Technical Names outside the dictionary.
- **Established terms of art.** `garbage collection` is the name of the thing. Do not "simplify" it to `automatic memory cleanup`.

When the prose around code is wrong, fix the prose and leave the code alone.

## The rules

### 1. One word, one meaning

Each word carries one sense throughout the document. Each concept gets one word. Do not alternate between *function*, *routine*, *method*, and *subroutine* for the same thing — choose one and hold it for the whole document.

Prefer the shortest common word. The test: would a competent reader with limited English know this word without a dictionary?

| Avoid | Use |
|---|---|
| utilise, employ, leverage | use |
| perform, execute, conduct | do, run |
| terminate, cease | stop, end |
| prior to, in advance of | before |
| in order to | to |
| a number of, numerous | many, some |
| commence, initiate | start |
| obtain, acquire | get |
| sufficient | enough |
| endeavour, attempt | try |
| approximately | about |

Use a word as one part of speech only. If *test* is a noun in your document, write "do a test", not "to test the value".

### 2. Short sentences

Split at 20 words (procedural, safety) or 25 (descriptive). The conjunction is almost always the seam — cut at *and*, *but*, *however*, *which*, *because*, or the dash.

One idea per sentence. One instruction per sentence. Never join two steps with *and*.

Paragraphs: 6 sentences maximum. In descriptive text, vary sentence length so the prose does not read like a machine wrote it.

### 3. Active voice, named actor

Passive voice hides who acts. In a procedure that is dangerous — the reader cannot tell whether the system does it or they do.

> The configuration file is read at startup.

→ Who reads it?

> The server reads the configuration file at startup.

Passive is acceptable only when the actor is genuinely unknown or irrelevant, and descriptive text tolerates it more than procedures do. Procedures: active, always.

### 4. Approved verb forms only

Use the infinitive, the imperative, the simple present, the simple past, the future, and the past participle **as an adjective**. Nothing else.

- **No `-ing` forms.** Not as a gerund, not as a continuous tense. Exception: part of a Technical Name (`operating system`, `floating point`).
  - "The system is processing the request" → "The system processes the request."
  - "Before installing the driver" → "Before you install the driver".
- **No past participle as a verb.** "The file has been deleted" → "The system deleted the file." As an adjective it is fine: "the deleted file".

### 5. Break noun clusters

Three or more stacked nouns are ambiguous. The reader cannot tell which noun modifies which. Put the prepositions back.

- `collision resolution strategy` → `a method to resolve collisions`
- `database connection pool timeout error` → `an error from a timeout in the pool of database connections`

Two nouns are usually fine. Three is the ceiling. Four is never acceptable.

### 6. Keep the articles

STE forbids telegraphic style. Write *the*, *a*, *an* wherever grammar allows.

> Remove filter. Install new filter.

→

> Remove the filter. Install a new filter.

### 7. Say must, can, will — not should, may

Modal verbs carry legal and safety weight. Vague ones make a requirement sound optional.

| Instead of | Write | Meaning |
|---|---|---|
| should, ought to | **must** | required |
| may, might, is able to | **can** | permitted or possible |
| shall | **must** or **will** | requirement or future |

Keep *should* only where you genuinely mean advice, not a rule.

### 8. Warnings come first

A warning after the step is useless — the reader has already run the command.

Order: **warning → consequence → preventive action → instruction.**

> ⚠️ **Warning:** `git reset --hard` removes all uncommitted changes in the working directory. You cannot recover them. Commit or stash your work first.
>
> To move the branch to an earlier commit, run `git reset --hard <commit>`.

Use **Warning** for harm to people or unrecoverable data loss. Use **Caution** for damage to equipment or recoverable loss. Use **Note** for anything else.

### 9. Cut the filler

Delete on sight: *simply*, *just*, *basically*, *actually*, *of course*, *obviously*, *it should be noted that*, *it is important to note that*, *as we can see*, *very*, *quite*, *rather*.

*Simply* and *just* also insult the reader who is stuck.

### 10. Give definitions their own sentence

A definition buried in a dash or a parenthesis gets skipped. Promote it.

> …when two keys map to the same index — an event known as a collision — the table…

→

> Two different keys can convert to the same index. This is a collision.

## Structure

Prose is the wrong container for some content. Convert it:

- **Branching or parallel options** → vertical list
- **A comparison with parallel structure** → table, one row per dimension
- **Ordered steps** → numbered list, imperative verb first
- **A rule with exceptions** → the rule, then the exceptions as a list

Front-load. Put the conclusion in the first sentence, then the detail. A reader who stops after one line must still get the main point.

## Workflow

1. Classify each block: procedural, descriptive, or safety.
2. Mark what is exempt — code, quotes, Technical Names.
3. Split every sentence over the limit.
4. Convert passive to active and name the actor.
5. Remove `-ing` forms and unapproved verb tenses.
6. Replace long words with the short equivalents in the table above.
7. Break noun clusters of three or more.
8. Move warnings before their steps.
9. Delete filler.
10. Convert branching prose to lists or tables.
11. Re-read for one word, one meaning across the whole document.

Step 11 is last on purpose. Terminology drift is only visible once the sentences are short enough to compare.

## When rules conflict with meaning

Meaning wins. If splitting a sentence loses a causal link the reader needs, keep the link and make it explicit with a short second sentence ("This happens because…"). Never let a rewrite make the text wrong or lose information the reader needs.

Do not rewrite a quotation to fit the rules. Quote it, then explain it in STE.
