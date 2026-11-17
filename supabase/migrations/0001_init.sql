-- ThreatLens AI - initial Supabase schema (0001_init.sql)
-- ============================================================
-- Apply ONCE via the Supabase Dashboard -> SQL Editor -> New query,
-- paste this file, Run. It is idempotent: re-running is safe.
--
-- Creates:
--   public.profiles  - one row per auth user (display name)
--   public.scans     - per-user scan records (owned, RLS-protected)
--   a signup trigger that creates the profile automatically
--
-- Security model (least-privilege):
--   * RLS is ENABLED on both tables; the backend holds NO privileged key,
--     so every query runs under the caller's own JWT and is bound by the
--     policies below (user_id = auth.uid()).
--   * The anon role can read/write nothing at all.
-- ============================================================

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
    id           uuid primary key references auth.users (id) on delete cascade,
    display_name text check (char_length(display_name) <= 60),
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

comment on table public.profiles is
  'Per-user profile. Row is created by the handle_new_user trigger at signup.';

-- ---------------------------------------------------------------------------
-- scans
-- ---------------------------------------------------------------------------
create table if not exists public.scans (
    id                text primary key,
    user_id           uuid not null references auth.users (id) on delete cascade,
    created_at        timestamptz not null default now(),
    url               text not null,
    classification    text not null
                      check (classification in
                        ('likely_benign', 'suspicious', 'high_risk')),
    binary_prediction text not null check (binary_prediction in
                        ('phishing', 'benign')),
    risk_score        integer not null check (risk_score between 0 and 100),
    probability       real not null check (probability >= 0 and probability <= 1),
    model_version     text not null,
    result_json       jsonb not null
);

comment on table public.scans is
  'Scan records. Ownership is enforced by RLS (user_id = auth.uid()). '
  'Legacy single-user records are NOT migrated: unowned history stays local.';

create index if not exists idx_scans_user_created
    on public.scans (user_id, created_at desc);
create index if not exists idx_scans_user_classification
    on public.scans (user_id, classification);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.scans    enable row level security;

-- Force RLS even for table owners (defence in depth).
alter table public.profiles force row level security;
alter table public.scans    force row level security;

-- profiles: users may see and edit only their own row.
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
    for select to authenticated
    using (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own" on public.profiles
    for insert to authenticated
    with check (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
    for update to authenticated
    using (auth.uid() = id)
    with check (auth.uid() = id);

drop policy if exists "profiles_delete_own" on public.profiles;
create policy "profiles_delete_own" on public.profiles
    for delete to authenticated
    using (auth.uid() = id);

-- scans: users may act only on their own records. There is deliberately NO
-- anon policy: anonymous roles can never read, insert, update or delete.
drop policy if exists "scans_select_own" on public.scans;
create policy "scans_select_own" on public.scans
    for select to authenticated
    using (auth.uid() = user_id);

drop policy if exists "scans_insert_own" on public.scans;
create policy "scans_insert_own" on public.scans
    for insert to authenticated
    with check (auth.uid() = user_id);

drop policy if exists "scans_delete_own" on public.scans;
create policy "scans_delete_own" on public.scans
    for delete to authenticated
    using (auth.uid() = user_id);

drop policy if exists "scans_update_own" on public.scans;
create policy "scans_update_own" on public.scans
    for update to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Belt and braces: no direct grants for anon on either table.
revoke all on public.profiles from anon;
revoke all on public.scans    from anon;

-- grants for the authenticated role (Data API access through RLS)
grant usage on schema public to authenticated;
grant select, insert, update, delete on public.profiles to authenticated;
grant select, insert, update, delete on public.scans    to authenticated;

-- ---------------------------------------------------------------------------
-- Auto-create a profile at signup (updated_at trigger included)
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
    insert into public.profiles (id, display_name)
    values (
        new.id,
        nullif(left(coalesce(new.raw_user_meta_data ->> 'display_name', ''), 60), '')
    )
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists profiles_touch_updated_at on public.profiles;
create trigger profiles_touch_updated_at
    before update on public.profiles
    for each row execute procedure public.touch_updated_at();
