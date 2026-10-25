# Slate

**A lineup is not a list. It is a handful of rooms.**

Live: [https://slate-mjuq.onrender.com](https://slate-mjuq.onrender.com)

When you choose titles one at a time, several slots can end up reaching the same audience. Slate looks at the lineup as a whole and shows which titles reach the same people, which reach audiences nothing else does, and which appeal to more than one audience group.

Built on Qloo's Insights API for the Qloo Agentic Hackathon 2026.

![Twelve comedy shows in four groups, with a bridge and two outliers](docs/figure.png)

---

## The problem

A festival programmer reads four hundred films and picks twenty, judging each one on its own merits. Nothing in that process asks what the twenty do together. Four of them can serve the same crowd, and the programmer has no way to see it, because the overlap is a property of the set and not of any film in it.

The same problem shows up anywhere people have to choose a small lineup from a much larger pool. A broadcaster might be deciding what to put on its schedule, an airline selecting from a larger entertainment catalogue, or a conference choosing which speakers make the final programme.

Slate has been tested on films, music, books, podcasts and TV shows.

## What Slate does

Give it four to twenty-four titles. It asks Qloo how each one relates to the others, builds a distance between every pair, and finds the groups.

Then it marks two things:

**Bridges.** A film close in taste to two different groups at once. It sits between them, so people drawn to one are more likely to find something in the other. Instead of needing a separate film for each group, one slot can reach both.

**Outliers.** A film that covers an audience with a distinct taste from the rest of the lineup. It covers some of its group’s audience, and some that nothing else in the lineup covers.

From the workspace, you can ask four things:

#### Fit it into fewer slots

Reduce the number of slots and find the best set to keep.

#### Find a title that adds a new group

Look for a new title that reaches a group the lineup is missing.

#### Check a new title against the lineup

Propose a title and see where it sits and what it changes.

#### Compare titles before adding

Compare several candidates and see which set does most for the lineup.

Each one gives you a brief you can download.

## The agent

The second of those four is the agentic part. It runs up to two rounds, and each round does the same five things:

1. Looks at the lineup's current shape.
2. Picks the title the lineup would miss least.
3. Asks Qloo for candidates unlike anything already there.
4. Adds each one to the full lineup and works the groups out again from scratch, so nothing is judged in isolation.
5. Keeps a swap only if the result is measurably better.

Round two starts from the lineup round one produced. If nothing clears the bar, Slate says so rather than offering the least bad option.

Every step is recorded, so you can see what it looked at, what it rejected and why.

## Why Qloo

Remove Qloo and nothing is left. The distance between two titles is built entirely from Qloo's affinity rankings: ask about each title, see where it places the others, average the two directions. Groups, bridges, outliers and every answer the agent gives come from that one number.

Nothing here could be done with a genre tag or a release date. We tested it, and the evidence is shown below.

## What we checked

Qloo's rankings are a claim about taste. To see whether they describe how people actually behave, Slate used MovieLens: 32 million film ratings from a research group at the University of Minnesota, with no connection to Qloo.

**The groups hold.** Two lineups MovieLens covers well were grouped as usual. Every possible pair of films was measured for shared audience. Pairs Slate put in the same group averaged 0.35; pairs it split apart averaged 0.24. Scrambling which film sat in which group ten thousand times never produced a gap that large.

**The distance behind them holds.** The further apart Slate places two films, the less their audiences overlap: −0.650 across 55 pairs. The films' own popularity scores +0.251. Hence, Slate is reading shared audience, not fame.

**Metadata cannot do it.** Against the same data, Slate’s distance scored a correlation of −0.498 against how much viewers agreed. Shared genres manage +0.038, release year −0.139, popularity +0.060. This means Slate’s distance predicts agreement far better than metadata does.

**The groups survive the lineup changing.** Remove any one title and redo the whole analysis. The experiment gave adjusted Rand index scores of +0.97, +0.86, +0.76 and +0.74 across the four sample lineups.

**A bridge is not just a popular film.** Across 62 films, how central a title is to the lineup's structure correlates with its popularity at +0.08, which is nothing.

All of these are reproducible from `scripts/`. The evidence section of the site shows them with the numbers and the method.

## Honest limits

Distance measures shared taste, not attendance, revenue or the number of people reached.

The bridge and outlier claims about audience are inferences from taste adjacency.

## Running it

Requires Python 3.10 or later.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put your Qloo key in `.env`, then:

```bash
python3 scripts/warm_cache.py
python3 -m uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

`warm_cache.py` makes about a hundred live calls and fills `data/cache`, so later runs of the sample lineups cost nothing.

Hackathon keys only work against [https://hackathon.api.qloo.com](https://hackathon.api.qloo.com).

### PDF download

The PDF download also needs Pango, which pip cannot install:

- macOS: `brew install pango`
- Ubuntu: `apt install libpango-1.0-0 libpangoft2-1.0-0`

Without it, the button prints instead, producing the same document.

### Reproducing the evidence

MovieLens is a 1 GB download and is not in the repo. Put `ml-32m/` under `data/`, then:

```bash
python3 scripts/probe_groups.py       # do the groups match behaviour
python3 scripts/probe_overlap.py      # does distance predict shared audience
python3 scripts/probe_movielens.py    # and does agreement follow
python3 scripts/probe_stability.py    # do groups survive a title leaving
python3 scripts/probe_bridge.py       # is a bridge just a popular film
python3 scripts/probe_censoring.py    # are short results from Qloo deterministic
```

These write into `data/validation.json`, which the site reads.

## Layout

```text
app/
  main.py       routes
  build.py      payloads, subset search, the comparison
  structure.py  clustering, outliers, bridges
  matrix.py     distances from Qloo rankings
  agent.py      the swap loop
  paper.py      the printable briefs
  store.py      workspaces
  qloo.py       the API client

static/
  index.html    the landing page
  app.js        the figure and the evidence
  work.js       the workspace

data/
  lineups/      the sample lineups
  examples/     what "Use an example" offers

scripts/        the probes and the cache warmer
tests/          the test suite
```

## Licence

MIT. See `LICENSE`.