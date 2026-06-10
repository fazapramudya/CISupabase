-- ============================================================
-- CrewInspector Seafarer Statistics - Supabase Schema
-- Run this in the Supabase SQL Editor to create all tables.
-- If upgrading from v1: run schema_add_country_rank.sql instead.
-- ============================================================

-- Tracks each automation run
CREATE TABLE scrape_runs (
    id           bigserial PRIMARY KEY,
    started_at   timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    status       text NOT NULL DEFAULT 'running'  -- 'running' | 'completed' | 'failed'
);

-- Headcount broken down by country per run
CREATE TABLE seafarer_by_country (
    id             bigserial PRIMARY KEY,
    run_id         bigint NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
    country_name   text NOT NULL,
    country_code   char(3),
    active_count   integer NOT NULL DEFAULT 0,
    inactive_count integer NOT NULL DEFAULT 0,
    total_count    integer NOT NULL DEFAULT 0,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- Headcount broken down by rank per run (only ranks with count > 0)
CREATE TABLE seafarer_by_rank (
    id             bigserial PRIMARY KEY,
    run_id         bigint NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
    rank_name      text NOT NULL,
    rank_id        integer,
    active_count   integer NOT NULL DEFAULT 0,
    inactive_count integer NOT NULL DEFAULT 0,
    total_count    integer NOT NULL DEFAULT 0,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- Headcount broken down by country AND rank per run
CREATE TABLE seafarer_by_country_rank (
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

-- Indexes
CREATE INDEX idx_country_run        ON seafarer_by_country(run_id);
CREATE INDEX idx_country_name       ON seafarer_by_country(country_name);
CREATE INDEX idx_country_code       ON seafarer_by_country(country_code);
CREATE INDEX idx_rank_run           ON seafarer_by_rank(run_id);
CREATE INDEX idx_rank_name          ON seafarer_by_rank(rank_name);
CREATE INDEX idx_cr_run             ON seafarer_by_country_rank(run_id);
CREATE INDEX idx_cr_country         ON seafarer_by_country_rank(country_code);
CREATE INDEX idx_cr_rank            ON seafarer_by_country_rank(rank_id);
