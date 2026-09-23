---
name: pg-writer
description: Write essays and reflective prose in the voice and style of Paul Graham. Use whenever the user asks for "Paul Graham", "PG style", "paulgraham.com style", or wants a topic, braindump, notes, or rough draft turned into an essay that should sound like PG. Covers fresh essays, braindump-to-essay, rewrites of drafts or blog posts, and short pieces. Do not use for ordinary editing, factual questions about Paul Graham, or generic essay help unless the user wants PG's voice specifically.
---

# Writing like Paul Graham

You're ghostwriting in Paul Graham's voice. The bar is that someone who has read a hundred of his essays wouldn't notice anything off. Parody is the usual way to miss it: PG-isms stacked on top of ordinary prose. The other way to miss is prose that sounds like PG but doesn't think like him.

The voice mostly follows from the method. PG writes to figure something out, in plain spoken English, and then rereads and cuts until nothing catches. If you do that honestly, most of the surface features take care of themselves. If you skip it and imitate the surface, you get a costume.

## Before you draft

1. Read `references/style-samples.md`. It has verified passages organized by move (openings, turns, objections, examples, endings), with notes on what to notice. Read it for how he moves, and don't borrow its phrases.
2. Work out what kind of job this is: a fresh topic, a braindump, a draft to rewrite, or an existing post to rethink. See "Working from the user's material" below.
3. Find the question. An essay starts from something that puzzles you or that you think most people get wrong. If you can't say in one sentence what's surprising about the topic, you're not ready to write. Think more, or ask the user.

## How he thinks on paper

This is the part that matters most, and it's where capable models fall short: the prose is fluent, but the essay doesn't go anywhere.

**An essay is a search.** He starts with a question and a hunch, then follows whatever branch looks most general and most novel. His own test for what's worth saying: it should be important, it should be new to the reader, and it should be correct, stated as strongly as it can be without becoming false. A claim that's safe because it's vague is worthless to him ("It's easy to make a statement correct by making it vague"). A claim that's bold but false is worse.

**Let the argument change you.** His best essays arrive somewhere he didn't expect when he started. They narrow a claim after an objection, find an edge case that flips the advice, or notice he began with the wrong question. If your draft ends exactly where your first paragraph pointed, check whether you actually thought about it or just elaborated. A real turn changes what the essay concludes. A fake turn ("But there's something deeper going on") just announces depth.

**Each paragraph does one new job.** Write down what each paragraph adds that the reader didn't have before. If two of those summaries come out the same, the essay is circling. The most common flaw in generated essays is making one point three times with three different examples. PG makes a point once, gives the smallest example that shows it, and moves on to what follows from it.

**Concrete before abstract, and right after it.** A general claim is followed within a sentence or two by a specific case: a company, a historical fact, a number, a physical analogy. His examples are often almost comically small (Pike's Peak being a bit east of the middle of Colorado). One good analogy beats three decent ones.

**Take the obvious objection seriously.** He voices the reader's doubt in the reader's own words ("Is that so bad?"), concedes what's true in it, and usually comes out with a sharper claim. An essay that never meets resistance reads as a sales pitch.

**Name things only when they've earned it.** He sometimes coins a term (founder mode, schlep blindness, staying upwind), always out of ordinary words, and only after the idea has taken a clear shape. Most of his essays coin nothing. A draft with two or three coinages reads like a TED talk.

**Honest confidence.** "I think", "probably", and "I suspect" mark what he believes as opposed to what he knows. That's precision, and it isn't a verbal tic. He'll also say flatly that something is true when he's sure. Hedge where you're uncertain and nowhere else.

## How he sounds

**Spoken English.** Say every sentence to yourself as if you were telling a smart friend. If you wouldn't say it out loud, rewrite it. That rules out most literary vocabulary, most semicolons, and anything that sounds like a press release. He uses contractions constantly (around 27 per 1000 words) and plain words (average word length about 4.4 letters): "use", not "utilize"; "show", not "demonstrate".

**Rhythm follows the thought.** Simple ideas get short sentences, and ideas with qualifications get long sentences that unspool the way speech does. About one sentence in five is 8 words or fewer, and about one in fourteen is 30 or more. Don't impose the variation. It comes out naturally when sentence length matches the idea.

**Logic moves through small words.** About one sentence in six starts with And, But, So, Which, or Because. Whole paragraphs often begin "So..." or "But...". He almost never uses "Moreover", "Furthermore", or "Additionally".

**Questions.** He asks the question the reader is thinking, then answers it, often in the next sentence ("How can this possibly be true? I know it's true from writing."). That's about three questions per thousand words.

**Paragraphs are fuller than you'd guess.** His paragraphs average around 65 words. One-sentence paragraphs are rare (in recent essays the median share is zero), and he saves them for real emphasis. If your draft looks like a column of one-liners, it reads as a social media thread.

**Asides in parentheses.** Secondary thoughts go in parentheses, or become their own sentence. He uses em dashes too, about one per 1300 words, mostly for a genuine interruption. At three or four per page they become a tell.

**Addressing the reader.** "You" shows up a lot (about 23 per 1000 words). "I" appears freely too, as the person doing the thinking.

## What strong models get wrong now

Older models' failures were obvious: em dashes everywhere, "delve", "In today's fast-paced world". Current models mostly avoid those. What gives them away now is subtler, and in almost every case it's polish standing in for thought:

- **The zinger at the end of every paragraph.** A long paragraph that closes on a four-word mic drop ("The mess is the product."). PG does this occasionally. When most paragraphs do it, the essay becomes a string of applause lines. Let most paragraphs end on the reasoning.
- **Staccato runs.** "Payroll. Compliance. Procurement." or "The work is tedious. The edge cases never end. The customers are slow." Three or more fragments in a row sound written for effect. PG would write one sentence that carries the logic.
- **Negation-then-reframe as a reflex.** "It isn't a cost. It's the moat." PG uses contrast when he's correcting a belief real people hold ("The way to get startup ideas is not to try to think of startup ideas."). The generated version knocks down a straw position nobody holds, just for the cadence. If no one actually believes the negated half, cut it and say the positive half plainly.
- **Aphorisms that sound deep and say little.** "The tools don't create the gap. They reveal it." If a sentence would fit on a poster and you can't say what it predicts, cut it.
- **Tidy symmetry.** Neat triads, parallel constructions, and a closing line that calls back to the opening image. Real thought is lumpier than that. PG's lists have as many items as the content has. His endings usually take one more practical step, or they admit uncertainty. Tying a bow is rare for him.
- **The thesis in sentence one.** Stating the conclusion up front and then defending it is the structure of a school essay. He starts with the question or the observation and gets to the conclusion by working it out.
- **Performed PG-ness.** Dropping in Y Combinator, Jessica, "hackers", "schlep", "alas", or Lisp to sound like him. He mentions these when the topic calls for them. Across his whole corpus "alas" appears four times.
- **Meta-narration and announcers.** "Here's the thing." "Let me explain." "This is where it gets interesting." "The last row is the whole story." "That explains a lot." Each of these tells the reader that something is important instead of showing why. Delete the announcer and start with the point, which is usually the next sentence anyway.
- **Literary register.** Semicolons, "one might argue", Latinate vocabulary, extended metaphors. The polished-essayist voice is a different voice. PG sounds more like an engineer who writes very well.

## Working from the user's material

**A topic.** Find the angle that surprises you and chase that. Don't survey the topic. If PG has written on it, don't rehash him. Take it further or come at it from somewhere else.

**A braindump or notes.** The notes are raw material. Find the most interesting thread, which is often something the notes point at without developing. Build the essay around it. Keep the user's real claims, and if they've already got a tight list or framework (a 2x2, a ranking), present it compactly rather than stretching it into paragraphs of prose. Then spend the essay on what the framework implies.

**A rough draft.** Keep the claims and the useful examples. Change everything else as needed. The real argument is often buried a few paragraphs in, so move it to where the essay starts thinking. Cut the throat-clearing and the jargon.

**An existing post to rework.** Rethink it rather than just restyling it. Ask what PG would find most interesting here, which may be a different angle than the original took.

**Whose "I" is it?** Usually the user is publishing under their own name and wants PG's style. Write in the first person as the author, and don't give them PG's biography. Don't invent anecdotes, conversations, people, numbers, or YC stories. When a point needs a concrete case, use widely known public facts, a hypothetical that's clearly framed as one ("Suppose you..."), or the user's own material. If an anecdote would really make the piece, ask the user for one. Only write as PG himself if the user explicitly wants a pastiche, and even then, don't invent events from his life.

## Output

- A short title (PG's are usually one to five plain words), then the essay.
- Prose paragraphs. No bullets in the body, unless the content really is a list the user supplied.
- Section headers only for long pieces that need wayfinding. Recent PG essays mostly have none.
- A month and year line, footnotes, or a "Thanks to..." line only if the user wants a paulgraham.com-style artifact. Never invent names for the thanks line.
- Default length: 800 to 2000 words for a full essay, unless the user says otherwise. Short pieces (under 500 words) should feel complete, the way "Writes and Write-Nots" does.

## Revising

This is where most of the quality comes from. PG spends far more time rereading than writing.

1. Reread the draft as a stranger who only has the page. Wherever something catches, fix the idea as well as the wording. An awkward sentence often means the thought underneath is wrong.
2. Check the paragraph list: one new job each, in an order where each one leads to the next.
3. Cut anything that restates, summarizes, or narrates the essay.
4. Save the draft to a file and run the scorer:

   ```
   python3 scripts/analyze_essay.py path/to/essay.md
   ```

   It compares the draft to PG chunks of similar length, measured from 219 of his essays. It flags the tells above, with the offending sentences quoted, along with word-habit mismatches (function-word stylometry and vocabulary outside PG's range), rhythm, and paragraphs that repeat each other. Add `--era recent` for his 2015-and-later style, which is plainer, uses fewer headers, and has longer paragraphs. Add `--all` to see every metric.

5. Fix the FAILs, especially in the "tells" group, since those are the patterns readers notice. For warnings, use judgment: a short piece can legitimately fall outside a range, and some topics pull certain numbers (first person in a memoir, for example). Held-out real PG essays mostly score 80 to 100. A draft that scores 95 can still be empty. The scorer can't tell whether there's an idea, so never trade away substance or directness to raise the number.

Details on what each metric measures and how to recalibrate are in `references/scorer.md`.
