-- Investment Radar: ejecutar solo en tu proyecto privado de Supabase.
create table if not exists public.investment_radar_data (
 user_id uuid primary key references auth.users(id) on delete cascade,
 content jsonb not null,
 revision bigint not null default 1 check (revision>0),
 updated_at timestamptz not null default now()
);
alter table public.investment_radar_data enable row level security;
revoke all on public.investment_radar_data from anon;
grant select,insert,update on public.investment_radar_data to authenticated;
drop policy if exists ir_select on public.investment_radar_data;
create policy ir_select on public.investment_radar_data for select to authenticated using (user_id=(select auth.uid()));
drop policy if exists ir_insert on public.investment_radar_data;
create policy ir_insert on public.investment_radar_data for insert to authenticated with check (user_id=(select auth.uid()));
drop policy if exists ir_update on public.investment_radar_data;
create policy ir_update on public.investment_radar_data for update to authenticated using (user_id=(select auth.uid())) with check (user_id=(select auth.uid()));
-- Evita lecturas y modificaciones desde otros usuarios.
