-- Destructive privacy cleanup for databases that already contain the legacy digest.
-- Review and back up the target database before applying; automatic provisioning does not run this.

BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE public.qf_context_messages
    DROP COLUMN IF EXISTS content_sha256;
COMMIT;
