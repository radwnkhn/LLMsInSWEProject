-- US-26: who served each LLM attempt, so admins can see token usage and cost per analysis.
-- Token counts already exist (input_tokens, output_tokens). Cost is computed from these columns and the
-- price table in backend/app/llm_prices.json when it is shown, so no dollar amounts are stored here.
-- Attempts saved before this migration keep null provider/model and show an unknown cost.
alter table public.llm_attempts
  add column if not exists provider text,
  add column if not exists model text;

-- Cost summaries filter attempts by their analysis's creation time.
create index if not exists analyses_created_at on public.analyses (created_at);
