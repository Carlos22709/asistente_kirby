BEGIN;

CREATE TABLE IF NOT EXISTS public.gmail_thread_references (
    id SERIAL PRIMARY KEY,
    gmail_thread_id VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_gmail_thread_references_thread_id
    ON public.gmail_thread_references (gmail_thread_id);

ALTER TABLE public.tasks
    ADD COLUMN IF NOT EXISTS source_gmail_thread_ref_id INTEGER;

CREATE INDEX IF NOT EXISTS ix_tasks_source_gmail_thread_ref_id
    ON public.tasks (source_gmail_thread_ref_id);

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_tasks_source_gmail_thread_ref'
          AND conrelid = 'public.tasks'::regclass
    ) THEN
        ALTER TABLE public.tasks
            ADD CONSTRAINT fk_tasks_source_gmail_thread_ref
            FOREIGN KEY (source_gmail_thread_ref_id)
            REFERENCES public.gmail_thread_references (id)
            ON DELETE SET NULL;
    END IF;
END;
$migration$;

COMMIT;
