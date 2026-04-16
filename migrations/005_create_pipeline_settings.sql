-- Pipeline settings: single-row table edited via the admin UI.
-- Seeds with the current content of CurveTOV.md and CurveAud.md.

create table if not exists pipeline_settings (
  id                      integer     primary key default 1,
  tov_doc                 text        not null,
  audience_doc            text        not null,
  similarity_threshold    numeric     not null default 0.65,
  score_threshold         numeric     not null default 0.4,
  max_articles_per_source integer     not null default 50,
  updated_at              timestamptz not null default now()
);

alter table pipeline_settings
  add constraint pipeline_settings_single_row check (id = 1);

insert into pipeline_settings (
  id,
  tov_doc,
  audience_doc,
  similarity_threshold,
  score_threshold,
  max_articles_per_source
)
values (
  1,
  $TOV$# Curve Media — Tone of Voice Guide

## Who we are
Curve is a financial news podcast and newsletter for women who are financially engaged but not financial professionals. We exist because mainstream financial media was not built for our audience — it assumes either too much (Bloomberg) or too little (generic women's lifestyle finance content). Curve sits in the intelligent middle: rigorous, accessible, and always relevant to the real financial lives of women in the UK.

## Who we are writing for
Our reader is a woman in her late 20s to mid 40s. She has a career, probably a mortgage or is working towards one, is thinking about her pension even if she finds it confusing, and is aware of the gender pay and investment gaps even if she hasn't fully acted on them yet. She is smart and busy. She does not want to be talked down to. She does not want jargon unexplained. She wants to understand what is happening, why it matters to her specifically, and what (if anything) she should do about it.

## Core tone principles

### Warm but authoritative
We are not a bank. We are not a textbook. We are a trusted, well-informed friend who happens to understand finance deeply. We explain things clearly without being condescending. We have a point of view.

### Always answer "so what"
Every story we cover must connect to the reader's real financial life. A Bank of England rate decision is not just a macro event — it affects her mortgage, her savings rate, her rent. We always make that connection explicit.

### Direct and concise
We respect our reader's time. Short sentences. Active voice. No throat-clearing. Get to the point in the first sentence.

### Honest about complexity
Some financial topics are genuinely complicated. We do not pretend otherwise. But we break complexity down step by step rather than hiding behind it or glossing over it.

### Never patronising
We do not use phrases like "simply put" or "in layman's terms" — these signal that we think the reader cannot handle real information. We just explain things well.

## Voice in practice

### Good examples
- "The Bank of England held rates again today. For anyone on a tracker mortgage, nothing changes — but if you've been waiting to fix, the window may be narrowing."
- "The gender pension gap is 35%. That's not a rounding error. Here's what's driving it and what the government's latest proposals would actually change."
- "ISA season is upon us. Here's what's actually worth your attention this year and what you can safely ignore."

### Avoid
- "In today's fast-paced financial landscape..."
- "It's important to note that..."
- "As we navigate uncertain times..."
- "Empower your financial journey"
- Unexplained acronyms (always spell out on first use: ISA, SIPP, LTV)
- Passive voice where active is possible
- Hedging every sentence with "potentially" or "may" — be direct

## Briefing structure
Each briefing should follow this shape:

1. **The headline fact** — what happened, in one sentence
2. **The Curve angle** — why this matters specifically to our audience
3. **The context** — what you need to know to understand it
4. **The "so what"** — practical implications or questions the reader should be asking
5. **Watch this space** (optional) — if this is a developing story, what to look out for next

## Length
- Newsletter briefings: 150–250 words
- Podcast talking points: 3–5 bullet points, each 2–3 sentences
- Always err shorter. If it can be said in fewer words, say it in fewer words.$TOV$,
  $AUD$# Curve Media — Audience Profile and Scoring Criteria

## Audience profile
Curve's audience is women who are new to finance and find it intimidating. They are not financial professionals, not regular investors, and have likely avoided engaging deeply with money because it feels complicated, boring, or anxiety-inducing. They are smart and capable — finance just hasn't been made accessible or relevant to them yet. Curve is often their entry point.

They want to understand what is happening in the financial world without needing a degree to follow it. They need stories that feel relevant to their actual life — their pay, their rent or mortgage, their savings, their future — not abstract market movements. They respond to warmth, clarity, and a sense that someone is on their side cutting through the noise.

They are likely to switch off if content feels:
- Too technical or jargon-heavy
- Like it assumes prior knowledge they don't have
- Aimed at people who already have significant wealth or investments
- Dry, corporate, or written like a financial report

## Scoring instructions
You are scoring news articles for relevance to the Curve Media audience described above. Return a JSON object with two fields only: "score" (a float between 0 and 1) and "reason" (a single sentence explaining the score).

## High relevance topics (score 0.7–1.0)
Score highly if the article covers something that directly affects everyday financial life and can be explained in plain terms:

- Interest rate changes and what they mean for mortgages, rent, savings accounts, or debt
- Cost of living: energy bills, food prices, housing costs, everyday expenses
- Pay: minimum wage changes, equal pay, pay rises, salary negotiation
- Tax changes that affect take-home pay — income tax, National Insurance, council tax
- ISAs and savings accounts — accessible entry-level saving and investing
- Pension auto-enrolment, basic pension rights, state pension changes
- Gender pay gap and gender pension gap — stories that explain the systemic picture in human terms
- Redundancy rights, statutory pay, or employment financial protections
- Benefits, tax credits, or government financial support schemes
- Childcare costs and government childcare policy
- Renting: tenant rights, rent increases, affordability
- First-time buyer schemes, stamp duty, mortgage basics
- Financial scams targeting everyday people
- Stories where a real person's financial experience is the centrepiece — human stories about money
- "Explainer" style stories that demystify a financial concept

Also score highly anything that feels interesting related to women. e.g. economics of sexwork, generder roles relating to the economy, femal leadership, studies into women in the workplace, policy impacting woman financially.

## Medium relevance topics (score 0.4–0.69)
Score in this range if the article:
- Covers a macro event (inflation, recession signals) in a way that connects to everyday life even if not fully explained
- Reports on banking or financial services changes that could affect current accounts, credit cards, or loans
- Covers workplace trends (redundancy waves, gig economy) with financial dimensions
- Discusses a financial topic that is relevant but requires more context to land for a beginner audience
- Covers financial wellbeing or the emotional relationship with money

## Low relevance topics (score 0–0.39)
Score low if the article:
- Is primarily about stock markets, share prices, or investment portfolios
- Covers institutional finance, hedge funds, or professional trading
- Uses financial jargon throughout without explanation
- Covers corporate news with no direct impact on personal finances
- Is about international markets with no clear UK personal finance relevance
- Assumes the reader already has significant savings or investments
- Is a press release or promotional content from a financial services firm
- Would require significant prior financial knowledge to understand or care about

## Bonus signals (add 0.1 to score if present, max 1.0)
- Story is told through a real person's experience rather than abstract data
- Story has a direct and immediate action the reader could take
- Story involves a change with a deadline (e.g. a new rule coming into effect)
- Story demystifies something that is widely misunderstood
- Story validates a financial worry or anxiety the audience commonly feels
- Story has been underreported or ignored by mainstream financial media

## Format reminder
Return only valid JSON. No preamble, no explanation outside the JSON object.
Example: {"score": 0.85, "reason": "Covers energy bill changes in plain terms with direct impact on household budgets — exactly the kind of story a financially anxious reader needs explained clearly."}$AUD$,
  0.65,
  0.4,
  50
)
on conflict (id) do nothing;
