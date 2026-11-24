-- HomeworkBuddy – Supabase schema
-- Run this once in Supabase → SQL Editor → New query → Run.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table if not exists public.families (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  join_code   text not null unique,
  created_by  uuid not null references auth.users(id),
  created_at  timestamptz not null default now()
);

create table if not exists public.family_members (
  family_id    uuid not null references public.families(id) on delete cascade,
  user_id      uuid not null references auth.users(id) on delete cascade,
  display_name text not null,
  joined_at    timestamptz not null default now(),
  primary key (family_id, user_id)
);

create table if not exists public.children (
  id          uuid primary key,
  family_id   uuid not null references public.families(id) on delete cascade,
  name        text not null,
  class_name  text,
  color       text not null default '#C2410C',
  subjects    text[] not null default '{}',
  deleted     boolean not null default false,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists public.homework (
  id             uuid primary key,
  family_id      uuid not null references public.families(id) on delete cascade,
  child_id       uuid not null references public.children(id) on delete cascade,
  subject        text not null,
  language_level text,
  task           text not null default '',
  pages          text[] not null default '{}',
  unit           text,
  book           text,
  action         text,
  repeat_note    text,
  is_test        boolean not null default false,
  due_date       date not null,
  status         text not null default 'pending'
                 check (status in ('pending', 'done', 'checked')),
  done_at        timestamptz,
  image_paths    text[] not null default '{}',
  source_text    text,
  created_by     uuid references auth.users(id),
  deleted        boolean not null default false,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create table if not exists public.exams (
  id          uuid primary key,
  family_id   uuid not null references public.families(id) on delete cascade,
  child_id    uuid not null references public.children(id) on delete cascade,
  subject     text not null,
  title       text not null,
  exam_date   date,
  portions    text,
  image_path  text,
  deleted     boolean not null default false,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

alter table public.families add column if not exists aliases jsonb not null default '{}'::jsonb;

create index if not exists homework_family_updated on public.homework (family_id, updated_at);
create index if not exists exams_family_updated    on public.exams (family_id, updated_at);
create index if not exists children_family_updated on public.children (family_id, updated_at);

-- updated_at is always set by the server, so every phone can pull
-- "everything changed since my last sync".
create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at := clock_timestamp();
  return new;
end $$;

drop trigger if exists children_touch on public.children;
create trigger children_touch before insert or update on public.children
  for each row execute function public.touch_updated_at();
drop trigger if exists homework_touch on public.homework;
create trigger homework_touch before insert or update on public.homework
  for each row execute function public.touch_updated_at();
drop trigger if exists exams_touch on public.exams;
create trigger exams_touch before insert or update on public.exams
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------
-- Security: a phone can only see and change its own family's rows
-- ---------------------------------------------------------------------------

create or replace function public.is_family_member(fid uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.family_members
    where family_id = fid and user_id = auth.uid()
  );
$$;

alter table public.families       enable row level security;
alter table public.family_members enable row level security;
alter table public.children       enable row level security;
alter table public.homework       enable row level security;
alter table public.exams          enable row level security;

drop policy if exists families_read on public.families;
create policy families_read on public.families
  for select using (public.is_family_member(id));

drop policy if exists families_update on public.families;
create policy families_update on public.families
  for update using (public.is_family_member(id)) with check (public.is_family_member(id));

drop policy if exists members_read on public.family_members;
create policy members_read on public.family_members
  for select using (public.is_family_member(family_id));

drop policy if exists members_update_self on public.family_members;
create policy members_update_self on public.family_members
  for update using (user_id = auth.uid());

do $$
declare t text;
begin
  foreach t in array array['children', 'homework', 'exams'] loop
    execute format('drop policy if exists %1$s_all on public.%1$s', t);
    execute format(
      'create policy %1$s_all on public.%1$s for all
         using (public.is_family_member(family_id))
         with check (public.is_family_member(family_id))', t);
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- Create / join a family (called from the app)
-- ---------------------------------------------------------------------------

create or replace function public.create_family(family_name text, display_name text)
returns table (family_id uuid, join_code text)
language plpgsql security definer set search_path = public as $$
#variable_conflict use_column
declare
  code text;
  fid  uuid;
begin
  if auth.uid() is null then raise exception 'Not signed in'; end if;
  loop
    code := lpad((floor(random() * 1000000))::int::text, 6, '0');
    exit when not exists (select 1 from families f where f.join_code = code);
  end loop;
  insert into families (name, join_code, created_by)
    values (family_name, code, auth.uid()) returning id into fid;
  insert into family_members (family_id, user_id, display_name)
    values (fid, auth.uid(), display_name);
  return query select fid, code;
end $$;

create or replace function public.join_family(code text, display_name text)
returns uuid
language plpgsql security definer set search_path = public as $$
declare fid uuid;
begin
  if auth.uid() is null then raise exception 'Not signed in'; end if;
  select id into fid from families where join_code = trim(code);
  if fid is null then raise exception 'Wrong family code'; end if;
  insert into family_members (family_id, user_id, display_name)
    values (fid, auth.uid(), display_name)
    on conflict (family_id, user_id) do update set display_name = excluded.display_name;
  return fid;
end $$;

revoke all on function public.create_family(text, text) from public, anon;
revoke all on function public.join_family(text, text) from public, anon;
grant execute on function public.create_family(text, text) to authenticated;
grant execute on function public.join_family(text, text) to authenticated;

-- ---------------------------------------------------------------------------
-- Cheap "has anything changed?" check (the app asks every few seconds)
-- ---------------------------------------------------------------------------

create or replace function public.family_version(fid uuid) returns text
language sql stable set search_path = public as $$
  select coalesce(max(t)::text, '') || '|' || (select count(*) from family_members where family_id = fid)
  from (
    select max(updated_at) t from children where family_id = fid
    union all select max(updated_at) from homework where family_id = fid
    union all select max(updated_at) from exams where family_id = fid
  ) x;
$$;

-- ---------------------------------------------------------------------------
-- Permissions. New Supabase projects no longer open new tables to signed-in
-- users automatically, so grant them explicitly. Row Level Security above
-- still limits every user to their own family's rows.
-- ---------------------------------------------------------------------------

grant usage on schema public to authenticated;
grant select, insert, update, delete on public.children, public.homework, public.exams to authenticated;
grant select, update on public.families, public.family_members to authenticated;
grant execute on function public.is_family_member(uuid) to authenticated;
grant execute on function public.family_version(uuid) to authenticated;

-- ---------------------------------------------------------------------------
-- Storage
--   homework-images : private, files stored as <family_id>/<file>.jpg
--   app-updates     : public, holds latest.json and the APK files
-- ---------------------------------------------------------------------------

insert into storage.buckets (id, name, public)
  values ('homework-images', 'homework-images', false)
  on conflict (id) do nothing;
insert into storage.buckets (id, name, public)
  values ('app-updates', 'app-updates', true)
  on conflict (id) do nothing;

drop policy if exists hw_images_read on storage.objects;
create policy hw_images_read on storage.objects for select to authenticated
  using (bucket_id = 'homework-images'
         and public.is_family_member(((storage.foldername(name))[1])::uuid));

drop policy if exists hw_images_write on storage.objects;
create policy hw_images_write on storage.objects for insert to authenticated
  with check (bucket_id = 'homework-images'
              and public.is_family_member(((storage.foldername(name))[1])::uuid));

drop policy if exists hw_images_delete on storage.objects;
create policy hw_images_delete on storage.objects for delete to authenticated
  using (bucket_id = 'homework-images'
         and public.is_family_member(((storage.foldername(name))[1])::uuid));
-- app-updates needs no policy for reading (public bucket). Only the GitHub
-- build (service-role key) uploads to it.
