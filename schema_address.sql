-- seafarer_addresses
-- Populated by import_address_xls.py from the Address XLS files downloaded per country.
-- Each row is one seafarer; seaman_id is the unique identifier from CrewInspector.

create table if not exists seafarer_addresses (
    seaman_id   bigint primary key,
    rank        text,
    name        text,           -- first name
    surname     text,           -- display name (LASTNAME, FIRSTNAME MI.)
    relation    text,           -- e.g. 'seafarer', 'online applicant', 'pool seafarer'
    country     text,           -- country name as stored in CrewInspector
    country_code char(3),       -- ISO 3166-1 alpha-3 code (from the downloaded filename)
    city        text,
    county      text,
    street      text,
    postal_code text,
    email       text,
    phone       text,
    mobile      text,
    payroll_id  text,
    imported_at timestamptz default now()
);

create index if not exists seafarer_addresses_country_code_idx on seafarer_addresses (country_code);
create index if not exists seafarer_addresses_rank_idx          on seafarer_addresses (rank);
create index if not exists seafarer_addresses_relation_idx      on seafarer_addresses (relation);
