-- ============================================================
-- PAROT MULTI-USER COLLABORATION DATABASE MIGRATION
-- Version: 1.0
-- Date: 2026-02-13
-- Description: Adds multi-user meeting collaboration features
-- ============================================================

-- Connect to database
\c parot_db;

BEGIN;

-- ============================================================
-- 1. CREATE NEW TABLES
-- ============================================================

-- Table: meeting_participants
-- Stores which users are participants in which meetings
CREATE TABLE IF NOT EXISTS meeting_participants (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    meeting_id VARCHAR NOT NULL,
    user_id VARCHAR NOT NULL,
    role VARCHAR(50) DEFAULT 'participant' CHECK (role IN ('host', 'participant', 'viewer')),
    can_edit BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT fk_meeting_participants_meeting 
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    CONSTRAINT fk_meeting_participants_user 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_meeting_user UNIQUE(meeting_id, user_id)
);

-- Indexes for meeting_participants
CREATE INDEX IF NOT EXISTS idx_meeting_participants_meeting_id 
    ON meeting_participants(meeting_id);
CREATE INDEX IF NOT EXISTS idx_meeting_participants_user_id 
    ON meeting_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_meeting_participants_active 
    ON meeting_participants(meeting_id, is_active);

-- Table: meeting_invitations
-- Stores pending and responded invitations to meetings
CREATE TABLE IF NOT EXISTS meeting_invitations (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    meeting_id VARCHAR NOT NULL,
    inviter_user_id VARCHAR NOT NULL,
    invitee_user_id VARCHAR NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT fk_invitations_meeting 
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    CONSTRAINT fk_invitations_inviter 
        FOREIGN KEY (inviter_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_invitations_invitee 
        FOREIGN KEY (invitee_user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for meeting_invitations
CREATE INDEX IF NOT EXISTS idx_meeting_invitations_meeting_id 
    ON meeting_invitations(meeting_id);
CREATE INDEX IF NOT EXISTS idx_meeting_invitations_invitee 
    ON meeting_invitations(invitee_user_id, status);
CREATE INDEX IF NOT EXISTS idx_meeting_invitations_status 
    ON meeting_invitations(status);
CREATE INDEX IF NOT EXISTS idx_meeting_invitations_created 
    ON meeting_invitations(created_at DESC);

-- Table: realtime_transcript_updates
-- Stores real-time transcript updates for live collaboration
CREATE TABLE IF NOT EXISTS realtime_transcript_updates (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    meeting_id VARCHAR NOT NULL,
    speaker_label VARCHAR(100),
    text TEXT NOT NULL,
    timestamp_ms BIGINT NOT NULL,
    sequence_number INTEGER NOT NULL,
    is_final BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_realtime_updates_meeting 
        FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

-- Indexes for realtime_transcript_updates
CREATE INDEX IF NOT EXISTS idx_realtime_updates_meeting_id 
    ON realtime_transcript_updates(meeting_id);
CREATE INDEX IF NOT EXISTS idx_realtime_updates_sequence 
    ON realtime_transcript_updates(meeting_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_realtime_updates_timestamp 
    ON realtime_transcript_updates(meeting_id, created_at);

-- ============================================================
-- 2. MODIFY EXISTING TABLES
-- ============================================================

-- Add new columns to meetings table
ALTER TABLE meetings 
    ADD COLUMN IF NOT EXISTS is_collaborative BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_live BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS ended_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS host_user_id VARCHAR;

-- Add foreign key constraint for host_user_id if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_meetings_host'
    ) THEN
        ALTER TABLE meetings 
            ADD CONSTRAINT fk_meetings_host 
            FOREIGN KEY (host_user_id) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Add indexes for new meeting columns
CREATE INDEX IF NOT EXISTS idx_meetings_collaborative 
    ON meetings(is_collaborative, is_live);
CREATE INDEX IF NOT EXISTS idx_meetings_host 
    ON meetings(host_user_id);
CREATE INDEX IF NOT EXISTS idx_meetings_started 
    ON meetings(started_at);

-- ============================================================
-- 3. UPDATE EXISTING DATA (OPTIONAL)
-- ============================================================

-- Set host_user_id to user_id for existing meetings
UPDATE meetings 
SET host_user_id = user_id 
WHERE host_user_id IS NULL;

-- ============================================================
-- 4. CREATE HELPER FUNCTIONS (OPTIONAL)
-- ============================================================

-- Function to check if user is a participant
CREATE OR REPLACE FUNCTION is_meeting_participant(
    p_meeting_id VARCHAR,
    p_user_id VARCHAR
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM meeting_participants
        WHERE meeting_id = p_meeting_id 
        AND user_id = p_user_id 
        AND is_active = TRUE
    );
END;
$$ LANGUAGE plpgsql;

-- Function to check if user is host
CREATE OR REPLACE FUNCTION is_meeting_host(
    p_meeting_id VARCHAR,
    p_user_id VARCHAR
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM meetings
        WHERE id = p_meeting_id 
        AND (host_user_id = p_user_id OR user_id = p_user_id)
    );
END;
$$ LANGUAGE plpgsql;

-- Function to get active participant count
CREATE OR REPLACE FUNCTION get_active_participant_count(
    p_meeting_id VARCHAR
) RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COUNT(*) 
        FROM meeting_participants
        WHERE meeting_id = p_meeting_id 
        AND is_active = TRUE
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 5. GRANT PERMISSIONS (UPDATE USERNAME AS NEEDED)
-- ============================================================

-- Grant permissions on new tables
GRANT ALL PRIVILEGES ON TABLE meeting_participants TO postgres;
GRANT ALL PRIVILEGES ON TABLE meeting_invitations TO postgres;
GRANT ALL PRIVILEGES ON TABLE realtime_transcript_updates TO postgres;

-- Grant permissions on helper functions
GRANT EXECUTE ON FUNCTION is_meeting_participant TO postgres;
GRANT EXECUTE ON FUNCTION is_meeting_host TO postgres;
GRANT EXECUTE ON FUNCTION get_active_participant_count TO postgres;

-- ============================================================
-- 6. VERIFICATION
-- ============================================================

-- Verify new tables were created
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name IN ('meeting_participants', 'meeting_invitations', 'realtime_transcript_updates');
    
    IF table_count = 3 THEN
        RAISE NOTICE '✓ All 3 new tables created successfully';
    ELSE
        RAISE WARNING '✗ Expected 3 tables, found %', table_count;
    END IF;
END $$;

-- Verify new columns in meetings table
DO $$
DECLARE
    column_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO column_count
    FROM information_schema.columns 
    WHERE table_name = 'meetings' 
    AND column_name IN ('is_collaborative', 'is_live', 'started_at', 'ended_at', 'host_user_id');
    
    IF column_count = 5 THEN
        RAISE NOTICE '✓ All 5 new columns added to meetings table';
    ELSE
        RAISE WARNING '✗ Expected 5 columns, found %', column_count;
    END IF;
END $$;

-- Display summary
SELECT 
    'meeting_participants' as table_name,
    COUNT(*) as row_count
FROM meeting_participants
UNION ALL
SELECT 
    'meeting_invitations' as table_name,
    COUNT(*) as row_count
FROM meeting_invitations
UNION ALL
SELECT 
    'realtime_transcript_updates' as table_name,
    COUNT(*) as row_count
FROM realtime_transcript_updates;

COMMIT;

-- ============================================================
-- MIGRATION COMPLETE
-- ============================================================

\echo '============================================================'
\echo 'Migration completed successfully!'
\echo '============================================================'
\echo ''
\echo 'New tables created:'
\echo '  - meeting_participants'
\echo '  - meeting_invitations'
\echo '  - realtime_transcript_updates'
\echo ''
\echo 'Meetings table updated with new columns:'
\echo '  - is_collaborative'
\echo '  - is_live'
\echo '  - started_at'
\echo '  - ended_at'
\echo '  - host_user_id'
\echo ''
\echo 'Next steps:'
\echo '  1. Update backend files (models.py, schemas.py, crud.py)'
\echo '  2. Add new API endpoints to main.py'
\echo '  3. Update frontend files (types.ts, geminiService.ts)'
\echo '  4. Add ParticipantsPanel component'
\echo '  5. Test the implementation'
\echo ''
\echo 'See IMPLEMENTATION_GUIDE.md for detailed instructions'
\echo '============================================================'