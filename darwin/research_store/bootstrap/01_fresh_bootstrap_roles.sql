-- PID-004A adversarial-audit fix #2 (database privilege separation) --
-- FRESH BOOTSTRAP path (item 10).
--
-- Intended use: a `docker-entrypoint-initdb.d/` script for a brand-new,
-- genuinely empty postgres:16-alpine data volume. The official postgres
-- image runs every *.sql/*.sh file under docker-entrypoint-initdb.d
-- exactly once, in filename order, authenticated as whatever
-- POSTGRES_USER the container was configured with -- THIS script assumes
-- that role is a TEMPORARY bootstrap administrator (e.g.
-- POSTGRES_USER=darwin_bootstrap_admin), never `darwin_app` itself. That
-- substitution is exactly the real defect this fix closes: today
-- POSTGRES_USER=darwin_app, which the official image always makes a
-- genuine superuser, so the application's own runtime credential IS a
-- superuser. A fresh deployment must never repeat that.
--
-- Full bootstrap sequence for a brand-new volume (see also
-- darwin/research_store/bootstrap/compose.role-separation.example.yaml):
--   1. Start the container with POSTGRES_USER=darwin_bootstrap_admin,
--      POSTGRES_DB=darwin, this script mounted under
--      docker-entrypoint-initdb.d/ -- runs automatically on first init.
--   2. Run `darwin migrate` using `darwin_migrator` credentials (the DSN
--      the migration runner uses in production) -- creates every table
--      0001-0007+, all owned by darwin_owner (see the `SET ROLE`
--      mechanism below -- no application code change is required for
--      this).
--   3. Run
--      darwin/research_store/bootstrap/02_grant_app_table_privileges.sql
--      once, as darwin_owner/darwin_migrator -- grants `darwin_app`
--      exactly the DML it needs, table by table. Only after this step is
--      `darwin_app` ready for `darwin_core`'s ordinary runtime
--      connections.
--
-- Secrets: this script never contains a real password. `darwin_migrator`
-- and `darwin_app` passwords are read from the process environment via
-- psql's `\getenv` (psql 10+) -- set DARWIN_MIGRATOR_BOOTSTRAP_PASSWORD /
-- DARWIN_APP_BOOTSTRAP_PASSWORD before this script runs (e.g. as
-- container secrets), never hardcoded here.

\getenv migrator_password DARWIN_MIGRATOR_BOOTSTRAP_PASSWORD
\getenv app_password DARWIN_APP_BOOTSTRAP_PASSWORD
\getenv dbname POSTGRES_DB

-- ---------------------------------------------------------------------------
-- 1. The three roles.
-- ---------------------------------------------------------------------------

-- darwin_owner: NOLOGIN. Owns the database/schema/tables/functions. Never
-- connected to directly by anything -- it exists purely as an ownership
-- anchor that darwin_migrator assumes (via SET ROLE, see below).
CREATE ROLE darwin_owner NOLOGIN;

-- darwin_migrator: LOGIN, separately secured from darwin_app. This is the
-- ONLY role `darwin migrate` should ever connect as in production.
CREATE ROLE darwin_migrator LOGIN PASSWORD :'migrator_password';

-- darwin_app: LOGIN, the role darwin_core's ordinary runtime connections
-- use. Explicitly stripped of every privilege class that would let
-- "ordinary application operation" bypass governed data protections
-- (PID-004A persistence directive item 7's own carve-out: "a superuser
-- could still ALTER TABLE ... DISABLE TRIGGER" -- darwin_app must not be
-- that superuser). Born this way from the very first connection -- there
-- is no earlier, more-privileged state to have downgraded from.
CREATE ROLE darwin_app LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- darwin_migrator may assume darwin_owner's privileges. Membership alone
-- (with the default INHERIT) is enough for ordinary privilege checks, but
-- object OWNERSHIP on CREATE is attributed to the current session's
-- current_user, not merely to an inherited role -- so an explicit,
-- automatic SET ROLE is what makes every table darwin_migrator creates
-- come out owned by darwin_owner (item 10's "ownership assigned to
-- darwin_owner from the first migration onward"), with ZERO change
-- required to darwin/research_store/migrations.py: this is a purely
-- role-level default, applied automatically at the start of every new
-- session authenticated as darwin_migrator.
GRANT darwin_owner TO darwin_migrator;
ALTER ROLE darwin_migrator SET role = 'darwin_owner';

-- darwin_app is deliberately NOT granted membership in darwin_owner or
-- darwin_migrator -- this is what makes `SET ROLE darwin_owner` /
-- `SET ROLE darwin_migrator` fail outright for a darwin_app connection
-- (see tests/integration/test_privilege_separation.py).

-- ---------------------------------------------------------------------------
-- 2. Ownership + schema hardening.
-- ---------------------------------------------------------------------------

-- The bootstrap admin (POSTGRES_USER) created the database at initdb
-- time -- hand it to darwin_owner immediately, before any application
-- table exists. On Postgres 15+ the `public` schema is owned by the
-- pseudo-role `pg_database_owner`, which dynamically resolves to
-- whichever role owns the database -- so this one statement also
-- retargets `public`'s effective ownership to darwin_owner, with no
-- separate `ALTER SCHEMA public OWNER TO ...` needed (see
-- 03_upgrade_existing_volume_to_role_separation.sql's header for the
-- empirical reason ordering this before any REASSIGN-style operation
-- matters).
ALTER DATABASE :"dbname" OWNER TO darwin_owner;

-- Nobody but darwin_owner (and darwin_migrator, via the SET ROLE above)
-- may create objects in the schema -- darwin_app only ever gets USAGE
-- (to look up/execute the tables darwin_migrator creates), never CREATE.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO darwin_app;
