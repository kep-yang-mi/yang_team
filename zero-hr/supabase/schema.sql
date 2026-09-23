-- Zero Company HR — Supabase schema (DATA_CONTRACT §13)
-- 멱등: create table if not exists / drop policy if exists + create policy.
-- 컬럼명은 data/clean/*.clean.csv · data/reference/org-chart.csv 헤더의 snake_case 변환이다.
-- RLS: 모든 테이블 enable. anon 은 report_snapshots select 만. service_role 은 전체.
-- 적용: bash supabase/apply_schema.sh  (psql "$SUPABASE_DB_URL" -f supabase/schema.sql)

begin;

-- ---------------------------------------------------------------- departments
-- 출처: data/reference/org-chart.csv
--   orgGroupCode,orgGroup,deptCode,department,formerNames,establishedOn
create table if not exists public.departments (
  dept_code       text primary key,
  department      text not null,
  org_group_code  text,
  org_group       text,
  former_names    text,
  established_on  date,
  updated_at      timestamptz not null default now()
);

-- ------------------------------------------------------------------ employees
-- 출처: data/clean/headcount-master.clean.csv (427행)
--   empId,name,gender,birthDate,ageBand,orgGroupCode,orgGroup,deptCode,department,
--   jobFamily,level,stage,employmentType,status,leaveType,leaveStart,hireDate,
--   contractEndDate,priorExperienceMonths,tenureYears,tenureYear,tenureBand,
--   totalExperienceYears,totalExperienceBand,unresolvedFlags,sourceRowIndex
create table if not exists public.employees (
  emp_id                   text primary key,
  name                     text,
  gender                   text,
  birth_date               date,
  age_band                 text,
  org_group_code           text,
  org_group                text,
  dept_code                text,
  department               text,
  job_family               text,
  level                    text,
  stage                    text,
  employment_type          text,
  status                   text,
  leave_type               text,
  leave_start              date,
  hire_date                date,
  contract_end_date        date,
  prior_experience_months  integer,
  tenure_years             numeric,
  tenure_year              integer,
  tenure_band              text,
  total_experience_years   numeric,
  total_experience_band    text,
  unresolved_flags         text,
  source_row_index         integer,
  updated_at               timestamptz not null default now()
);
create index if not exists employees_dept_code_idx on public.employees (dept_code);
create index if not exists employees_status_idx    on public.employees (status);

-- -------------------------------------------------------------------- to_plan
-- 출처: data/clean/to-plan.clean.csv (11행)
--   deptCode,department,orgGroupCode,toHeadcount,effectiveMonth
create table if not exists public.to_plan (
  dept_code        text primary key,
  department       text,
  org_group_code   text,
  to_headcount     integer,
  effective_month  text,
  updated_at       timestamptz not null default now()
);

-- ------------------------------------------------------------- planned_joiners
-- 출처: data/clean/planned-joiners.clean.csv (27행)
--   joinerId,name,deptCode,department,jobFamily,level,employmentType,gender,
--   birthDate,plannedHireDate,priorExperienceMonths,unresolvedFlags
create table if not exists public.planned_joiners (
  joiner_id                text primary key,
  name                     text,
  dept_code                text,
  department               text,
  job_family               text,
  level                    text,
  employment_type          text,
  gender                   text,
  birth_date               date,
  planned_hire_date        date,
  prior_experience_months  integer,
  unresolved_flags         text,
  updated_at               timestamptz not null default now()
);
create index if not exists planned_joiners_hire_date_idx on public.planned_joiners (planned_hire_date);

-- ------------------------------------------------------------- planned_leavers
-- 출처: data/clean/planned-leavers.clean.csv (19행)
--   empId,deptCode,plannedTerminationDate,separationType,separationReason,unresolvedFlags
create table if not exists public.planned_leavers (
  emp_id                    text not null,
  planned_termination_date  date not null,
  dept_code                 text,
  separation_type           text,
  separation_reason         text,
  unresolved_flags          text,
  updated_at                timestamptz not null default now(),
  primary key (emp_id, planned_termination_date)
);

-- --------------------------------------------------------------- cleansing_log
-- 출처: data/clean/cleansing-log.jsonl (127행)
--   {source,rowRef{사번,rowIndex},field,rawValue,correctedValue,rule,confidence,unresolved}
-- log_hash: 정규화 JSON 의 sha256 — 재실행 시 중복 적재를 막는 멱등 키(upsert on_conflict=log_hash)
create table if not exists public.cleansing_log (
  id               bigserial primary key,
  log_hash         text not null unique,
  source           text,
  row_ref          jsonb,
  field            text,
  raw_value        text,
  corrected_value  text,
  rule             text,
  confidence       numeric,
  unresolved       boolean,
  created_at       timestamptz not null default now()
);
create index if not exists cleansing_log_source_idx     on public.cleansing_log (source);
create index if not exists cleansing_log_unresolved_idx on public.cleansing_log (unresolved);

-- ------------------------------------------------------------- report_snapshots
-- payload 는 site/data/{product}.json 을 있는 그대로(바이트 동등 파싱 결과) 싣는다.
-- 페이지는 product 별 최신 created_at 1행만 읽는다 → 재적재는 append(=갱신), 삭제 없음.
create table if not exists public.report_snapshots (
  id          bigserial primary key,
  product     text not null,
  as_of_date  date,
  payload     jsonb not null,
  created_at  timestamptz not null default now()
);
create index if not exists report_snapshots_product_created_at_idx
  on public.report_snapshots (product, created_at desc);

-- ------------------------------------------------------------------------ RLS
alter table public.departments      enable row level security;
alter table public.employees        enable row level security;
alter table public.to_plan          enable row level security;
alter table public.planned_joiners  enable row level security;
alter table public.planned_leavers  enable row level security;
alter table public.cleansing_log    enable row level security;
alter table public.report_snapshots enable row level security;

-- service_role: 전체 권한 (seed.py · verify.py 가 쓰는 경로)
drop policy if exists departments_service_all      on public.departments;
create policy departments_service_all      on public.departments      for all to service_role using (true) with check (true);

drop policy if exists employees_service_all        on public.employees;
create policy employees_service_all        on public.employees        for all to service_role using (true) with check (true);

drop policy if exists to_plan_service_all          on public.to_plan;
create policy to_plan_service_all          on public.to_plan          for all to service_role using (true) with check (true);

drop policy if exists planned_joiners_service_all  on public.planned_joiners;
create policy planned_joiners_service_all  on public.planned_joiners  for all to service_role using (true) with check (true);

drop policy if exists planned_leavers_service_all  on public.planned_leavers;
create policy planned_leavers_service_all  on public.planned_leavers  for all to service_role using (true) with check (true);

drop policy if exists cleansing_log_service_all    on public.cleansing_log;
create policy cleansing_log_service_all    on public.cleansing_log    for all to service_role using (true) with check (true);

drop policy if exists report_snapshots_service_all on public.report_snapshots;
create policy report_snapshots_service_all on public.report_snapshots for all to service_role using (true) with check (true);

-- anon(브라우저 · config.js 의 publishable key): report_snapshots select 만.
-- employees 등 개인 식별 테이블에는 anon 정책을 만들지 않는다(pii-minimization-policy).
-- RLS enable + 정책 없음 = anon 접근 0행/거부. verify.py 가 이것을 확인한다.
drop policy if exists report_snapshots_anon_select on public.report_snapshots;
create policy report_snapshots_anon_select on public.report_snapshots for select to anon using (true);

-- PostgREST 가 쓰는 스키마/테이블 권한 (RLS 가 행 단위를 막는다)
grant usage on schema public to anon, authenticated, service_role;
grant select on public.report_snapshots to anon, authenticated;
grant all    on public.departments, public.employees, public.to_plan,
               public.planned_joiners, public.planned_leavers,
               public.cleansing_log, public.report_snapshots to service_role;
grant usage, select on all sequences in schema public to service_role;

commit;

-- PostgREST 스키마 캐시 리로드 (테이블 추가 후 PGRST205 방지)
notify pgrst, 'reload schema';
