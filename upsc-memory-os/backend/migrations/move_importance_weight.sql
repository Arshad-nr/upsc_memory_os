-- ============================================================
-- Migration: Move importance_weight from topics → user_topic_profiles
-- Run this ONCE on your Supabase SQL Editor
-- Date: 2026-06-07
-- ============================================================

-- Step 1: Add importance_weight to the personal user_topic_profiles table
-- Default is 0.5 (standard priority) for all existing rows
ALTER TABLE user_topic_profiles
    ADD COLUMN IF NOT EXISTS importance_weight FLOAT NOT NULL DEFAULT 0.5;

-- Step 2: Drop importance_weight from the global topics table
ALTER TABLE topics
    DROP COLUMN IF EXISTS importance_weight;

-- ============================================================
-- DONE. Verify with:
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'user_topic_profiles';
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'topics';
-- ============================================================
