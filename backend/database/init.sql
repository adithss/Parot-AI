-- Database initialization script for Parot
-- This script creates the database and necessary extensions

-- Create database (run this as postgres superuser)
-- CREATE DATABASE parot_db;

-- Connect to the database
\c parot_db;

-- Create extension for UUID generation (if needed)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Create meetings table
CREATE TABLE IF NOT EXISTS meetings (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id VARCHAR NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    audio_file_path VARCHAR(500),
    spectrogram_url VARCHAR(500),
    duration INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    meeting_date TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'completed',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_meetings_user_id ON meetings(user_id);
CREATE INDEX IF NOT EXISTS idx_meetings_created_at ON meetings(created_at);

-- Create speakers table
CREATE TABLE IF NOT EXISTS speakers (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    meeting_id VARCHAR NOT NULL,
    speaker_label VARCHAR(100) NOT NULL,
    speaker_name VARCHAR(255),
    total_speaking_time FLOAT,
    segment_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_speakers_meeting_id ON speakers(meeting_id);

-- Create transcripts table
CREATE TABLE IF NOT EXISTS transcripts (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    meeting_id VARCHAR NOT NULL,
    speaker_id VARCHAR,
    text TEXT NOT NULL,
    start_time FLOAT,
    end_time FLOAT,
    confidence FLOAT,
    sequence_number INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    FOREIGN KEY (speaker_id) REFERENCES speakers(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_transcripts_meeting_id ON transcripts(meeting_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_sequence ON transcripts(meeting_id, sequence_number);

-- Create summaries table
CREATE TABLE IF NOT EXISTS summaries (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    meeting_id VARCHAR UNIQUE NOT NULL,
    summary_text TEXT NOT NULL,
    key_points JSONB,
    topics TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_summaries_meeting_id ON summaries(meeting_id);

-- Create sentiment_analysis table
CREATE TABLE IF NOT EXISTS sentiment_analysis (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    meeting_id VARCHAR UNIQUE NOT NULL,
    overall_sentiment VARCHAR(50),
    highlights TEXT[],
    emotion_analysis JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sentiment_meeting_id ON sentiment_analysis(meeting_id);

-- Create action_items table
CREATE TABLE IF NOT EXISTS action_items (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    meeting_id VARCHAR NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_action_items_meeting_id ON action_items(meeting_id);

-- Create key_decisions table
CREATE TABLE IF NOT EXISTS key_decisions (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    meeting_id VARCHAR NOT NULL,
    decision TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_key_decisions_meeting_id ON key_decisions(meeting_id);

-- Grant permissions (adjust username as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_username;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_username;