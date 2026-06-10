-- Run this if you already have the v1 tables and just need to add
-- seafarer_by_country_rank (and remove the unused seafarer_totals).

DROP TABLE IF EXISTS seafarer_totals CASCADE;

CREATE TABLE IF NOT EXISTS seafarer_by_country_rank (
    id             bigserial PRIMARY KEY,
    run_id         bigint NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
    country_name   text NOT NULL,
    country_code   char(3),
    rank_name      text NOT NULL,
    rank_id        integer,
    active_count   integer NOT NULL DEFAULT 0,
    inactive_count integer NOT NULL DEFAULT 0,
    total_count    integer NOT NULL DEFAULT 0,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cr_run     ON seafarer_by_country_rank(run_id);
CREATE INDEX IF NOT EXISTS idx_cr_country ON seafarer_by_country_rank(country_code);
CREATE INDEX IF NOT EXISTS idx_cr_rank    ON seafarer_by_country_rank(rank_id);
