-- Read-only inspection using a valid Supabase DATABASE_URL or SQL Editor.
-- Does not retrieve user records or change the schema/data.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';

SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN (
    'opportunities', 'users', 'user_activity_events',
    'user_category_preferences', 'career_jobs', 'job_postings', 'housing_transactions'
  )
ORDER BY table_name, ordinal_position;

SELECT c.relname AS table_name, k.conname AS constraint_name,
       k.contype AS constraint_type, pg_get_constraintdef(k.oid) AS definition
FROM pg_constraint k
JOIN pg_class c ON c.oid = k.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN (
    'opportunities', 'users', 'user_activity_events',
    'user_category_preferences', 'career_jobs', 'job_postings', 'housing_transactions'
  )
ORDER BY c.relname, k.conname;

SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
    'opportunities', 'users', 'user_activity_events',
    'user_category_preferences', 'career_jobs', 'job_postings', 'housing_transactions'
  )
ORDER BY tablename, indexname;

SELECT c.relname AS table_name,
       c.relrowsecurity AS rls_enabled, c.relforcerowsecurity AS rls_forced
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN (
    'opportunities', 'users', 'user_activity_events',
    'user_category_preferences', 'career_jobs', 'job_postings', 'housing_transactions'
  )
ORDER BY c.relname;

SELECT 'opportunities' AS table_name, count(*) AS row_count FROM public.opportunities
UNION ALL
SELECT 'career_jobs', count(*) FROM public.career_jobs
UNION ALL
SELECT 'job_postings', count(*) FROM public.job_postings
UNION ALL
SELECT 'housing_transactions', count(*) FROM public.housing_transactions;

ROLLBACK;
