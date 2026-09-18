-- PID-004A adversarial-audit fix #2 (database privilege separation) --
-- EXISTING-VOLUME UPGRADE path (item 11) -- the harder, required half of
-- the fix.
--
-- Starting state this script assumes (== the real production darwin_sql
-- today, per /srv/darwin-deploy-build/compose.yaml): a single role named
-- `darwin_app`, created via the official postgres image's POSTGRES_USER
-- (which always makes that role a genuine superuser), OWNS the database/
-- schema/every table, and is the SAME credential darwin_core uses for
-- ordinary runtime queries -- with migrations 0001 through the current
-- HEAD already applied through it, and real PID-001/003/004 data already
-- persisted.
--
-- Ending state: three separated roles (darwin_owner / darwin_migrator /
-- darwin_app) exactly matching 01_fresh_bootstrap_roles.sql's model,
-- with EVERY pre-existing row untouched (this is an ownership +
-- privilege change only -- no DROP, no TRUNCATE, no CREATE DATABASE, no
-- data migration of any kind).
--
-- *** IMPORTANT DISCOVERY (recorded honestly, not quietly worked around):
-- the Architect's own directive describes this step as a `REASSIGN OWNED
-- BY darwin_app TO darwin_owner` followed by `ALTER ROLE darwin_app
-- NOSUPERUSER ...`. Neither literal statement actually works here, and
-- this is a genuine Postgres constraint, proven empirically against a
-- real postgres:16-alpine container while developing this script -- not
-- a misunderstanding of the SQL:
--
--   1. `REASSIGN OWNED BY darwin_app TO darwin_owner` fails outright:
--      "cannot reassign ownership of objects owned by role darwin_app
--      because they are required by the database system". The official
--      postgres image's `initdb --username=$POSTGRES_USER` always
--      assigns the FIXED, hardcoded bootstrap-superuser role OID (10) to
--      whichever name POSTGRES_USER is set to -- and
--      /srv/darwin-deploy-build/compose.yaml sets POSTGRES_USER to
--      `darwin_app` (exactly the bug this fix closes). Postgres refuses
--      `REASSIGN OWNED BY` for OID 10 unconditionally, because a large
--      amount of cluster-wide catalog state (spanning every database,
--      not just this one) is permanently pinned to the bootstrap role
--      and cannot be reassigned by any SQL statement, ever. Worked
--      around below with explicit, targeted `ALTER TABLE/FUNCTION/
--      SEQUENCE ... OWNER TO` statements instead of the blanket
--      REASSIGN -- those are NOT affected by the pin.
--   2. Even after every owned object has been reassigned away,
--      `ALTER ROLE darwin_app NOSUPERUSER` STILL fails: "permission
--      denied to alter role / DETAIL: The bootstrap user must have the
--      SUPERUSER attribute." Postgres hard-codes a rule that role OID 10
--      may never lose SUPERUSER, full stop -- independent of ownership,
--      independent of anything this script can grant/revoke.
--   3. Renaming darwin_app away (to work around point 2 by retiring the
--      identity rather than downgrading it in place) ALSO fails while
--      connected AS darwin_app: "session user cannot be renamed" --
--      Postgres refuses to let a role rename itself, regardless of
--      privilege.
--
-- Point 2 means a literal in-place downgrade of the EXISTING `darwin_app`
-- identity is architecturally impossible while it remains OID 10, and
-- point 3 means the retire-and-replace workaround needs a SECOND
-- identity to perform it from. The equivalent, fully-safe outcome is
-- achieved by temporarily, narrowly borrowing `darwin_migrator` for that
-- one purpose:
--   a. grant darwin_migrator SUPERUSER, but only for the few statements
--      that need it -- reconnect this session AS darwin_migrator (so the
--      "session user" is no longer darwin_app, unblocking the rename),
--      do the retire-and-replace, then immediately strip SUPERUSER back
--      off darwin_migrator again. darwin_migrator's FINAL state is
--      exactly as designed: LOGIN, NOSUPERUSER, a member of darwin_owner
--      it assumes via SET ROLE -- this is a scoped, temporary, fully
--      reversed elevation, not a change to the target role model;
--   b. rename the old OID-10 role out of the way and permanently disable
--      login on it (NOLOGIN + password cleared) -- it keeps an inert,
--      unusable SUPERUSER bit forever (Postgres cannot remove this), but
--      NOLOGIN means it can never be connected as, assumed via SET ROLE,
--      or used for anything at all again;
--   c. create a brand-new role named `darwin_app` (an ordinary role,
--      NOT OID 10) with the SAME password as before (read from
--      DARWIN_APP_UPGRADE_PASSWORD) -- darwin_core's existing DSN
--      continues to work completely unchanged; the new role is fully,
--      genuinely restrictable because it carries none of OID 10's
--      special-cased protections.
-- Every pre-existing table/function/sequence was already reassigned to
-- darwin_owner in step 2 BEFORE any of this (while still connected as
-- the original darwin_app, which is allowed to reassign objects IT
-- owns) -- reassignment tracks by OID, not by name, so the later rename
-- changes nothing about who owns what.
--
-- Idempotent-if-rerun: every statement below is safe to run again after a
-- partial or fully successful prior run (role/grant existence is checked
-- or the operation is naturally idempotent) -- this script does not
-- assume it is running for the first time.
--
-- Secrets: as with 01_fresh_bootstrap_roles.sql, no real password is
-- written here. This script assumes it is being run by an operator
-- already connected AS the existing darwin_app superuser (the only role
-- that currently exists and can perform CREATE ROLE); darwin_migrator's
-- new password and darwin_app's (unchanged, existing) password are both
-- read from the environment via `\getenv`, never hardcoded.
--
-- Usage: DARWIN_MIGRATOR_UPGRADE_PASSWORD=<new secret> \
--        DARWIN_APP_UPGRADE_PASSWORD=<darwin_app's EXISTING password --
--            keep it identical unless you are ALSO coordinating a
--            credential rotation with darwin_core's own config> \
--        psql "<darwin_app superuser DSN>" \
--            -f 03_upgrade_existing_volume_to_role_separation.sql

\getenv migrator_password DARWIN_MIGRATOR_UPGRADE_PASSWORD
\getenv app_password DARWIN_APP_UPGRADE_PASSWORD

-- ---------------------------------------------------------------------------
-- 1. Create darwin_owner and darwin_migrator (idempotent: skip if this
--    script has already partially run).
-- ---------------------------------------------------------------------------

SELECT 'CREATE ROLE darwin_owner NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'darwin_owner')
\gexec

SELECT format('CREATE ROLE darwin_migrator LOGIN PASSWORD %L', :'migrator_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'darwin_migrator')
\gexec

GRANT darwin_owner TO darwin_migrator;

-- ---------------------------------------------------------------------------
-- 2. THE critical step: transfer ownership of every object the CURRENT
--    darwin_app (still OID 10 at this point, still connected as itself --
--    which is fine, ownership transfer is not a rename) owns, to
--    darwin_owner. This is what actually closes the TRUNCATE/DISABLE
--    TRIGGER/DROP TABLE gap -- everything after this is tightening a
--    role that no longer owns anything. See the header above for why
--    this uses targeted ALTER ... OWNER TO statements rather than
--    REASSIGN OWNED BY.
-- ---------------------------------------------------------------------------

SELECT format('ALTER DATABASE %I OWNER TO darwin_owner', current_database())
\gexec

SELECT format('ALTER TABLE %I.%I OWNER TO darwin_owner', schemaname, tablename)
FROM pg_tables
WHERE schemaname = 'public' AND tableowner = 'darwin_app'
\gexec

SELECT format(
    'ALTER FUNCTION %I.%I(%s) OWNER TO darwin_owner',
    n.nspname, p.proname, pg_get_function_identity_arguments(p.oid)
)
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public' AND pg_get_userbyid(p.proowner) = 'darwin_app'
\gexec

SELECT format('ALTER SEQUENCE %I.%I OWNER TO darwin_owner', schemaname, sequencename)
FROM pg_sequences
WHERE schemaname = 'public' AND sequenceowner = 'darwin_app'
\gexec

-- ---------------------------------------------------------------------------
-- 3. Borrow darwin_migrator, temporarily, to retire the old darwin_app
--    (OID 10) and create a fresh one in its place (see the header
--    discovery above for exactly why this detour is necessary). This
--    elevation is undone in the same step, before this script finishes.
-- ---------------------------------------------------------------------------

ALTER ROLE darwin_migrator SUPERUSER;

\setenv PGPASSWORD :migrator_password
\connect - darwin_migrator
-- Belt-and-braces: if a PRIOR run of this script already applied
-- darwin_migrator's `SET role = 'darwin_owner'` session default (set at
-- the very end, below), a fresh connection would otherwise start with
-- current_user already switched away from the superuser session_user --
-- RESET ROLE guarantees this session has its own full (temporarily
-- granted) superuser privilege for the statements that follow,
-- regardless of run history.
RESET ROLE;

SELECT 'ALTER ROLE darwin_app RENAME TO darwin_retired_bootstrap_superuser'
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'darwin_app' AND oid = 10)
\gexec

-- NOLOGIN + a cleared password: this role can never be connected as,
-- impersonated via SET ROLE, or used for anything again -- its residual
-- SUPERUSER catalog bit (which Postgres will not let anyone remove) is
-- permanently inert as a result.
SELECT 'ALTER ROLE darwin_retired_bootstrap_superuser NOLOGIN PASSWORD NULL'
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'darwin_retired_bootstrap_superuser')
\gexec

SELECT format(
    'CREATE ROLE darwin_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
    :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'darwin_app')
\gexec

-- Idempotent re-run safety: if darwin_app already existed (a second run
-- of this script after the rename already happened), make sure it still
-- carries every restricted attribute.
ALTER ROLE darwin_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- De-elevate darwin_migrator immediately -- this is a normal (non-OID-10)
-- role, so stripping its own SUPERUSER attribute, even while connected
-- as itself, is fully permitted (only the rename/superuser-removal
-- restrictions above are specific to the bootstrap role).
ALTER ROLE darwin_migrator NOSUPERUSER;

-- Now that the temporary elevation is over, set darwin_migrator's
-- permanent session default -- every FUTURE connection as darwin_migrator
-- (i.e. every real `darwin migrate` run) automatically operates as
-- darwin_owner, with zero code change required in
-- darwin/research_store/migrations.py.
ALTER ROLE darwin_migrator SET role = 'darwin_owner';

-- ---------------------------------------------------------------------------
-- 4. Schema hardening -- identical to fresh bootstrap. Still running as
--    darwin_migrator, which inherits darwin_owner's privileges over the
--    schema it now owns (membership + default INHERIT is sufficient for
--    GRANT/REVOKE here -- no SET ROLE needed).
-- ---------------------------------------------------------------------------

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO darwin_app;

-- ---------------------------------------------------------------------------
-- 5. Grant the NEW darwin_app exactly the DML it needs, table by table --
--    shared with the fresh-bootstrap path so the two flows can never
--    drift apart.
-- ---------------------------------------------------------------------------

\ir 02_grant_app_table_privileges.sql

-- ---------------------------------------------------------------------------
-- Deliberately NOT done here (out of scope / a separate later step):
--   * Dropping darwin_retired_bootstrap_superuser outright. Postgres may
--     refuse to DROP ROLE the bootstrap superuser too (untested here --
--     NOLOGIN already makes it fully inert, so there is no operational
--     need to force the question); leaving it renamed-and-disabled is
--     sufficient and safer than guessing at an unproven DROP.
--   * Actually running this against the live production database/
--     deployment -- that is explicitly reserved for the dispatcher, with
--     Helm's coordination, as a later step.
-- ---------------------------------------------------------------------------
