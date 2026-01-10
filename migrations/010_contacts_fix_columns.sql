-- =====================================================
-- WhatsApp CRM - Fix Contacts Table Columns
-- Adds missing columns to contacts table
-- =====================================================

-- Add missing columns to contacts table
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS first_contact_at TIMESTAMP WITH TIME ZONE;

-- phone field needs to allow longer values for international numbers
ALTER TABLE contacts ALTER COLUMN phone TYPE VARCHAR(50);

-- name field compatibility - add if not exists (some DBs have 'full_name', others have 'name')
-- If full_name exists but name doesn't, rename it
DO $$
BEGIN
    -- Check if 'name' column doesn't exist but 'full_name' does
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'contacts' AND column_name = 'name'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'contacts' AND column_name = 'full_name'
    ) THEN
        -- Rename full_name to name
        ALTER TABLE contacts RENAME COLUMN full_name TO name;
    END IF;
    
    -- If neither exists, add name
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'contacts' AND column_name = 'name'
    ) THEN
        ALTER TABLE contacts ADD COLUMN name VARCHAR(255);
    END IF;
END $$;

-- Ensure name column can hold enough characters
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'contacts' AND column_name = 'name'
    ) THEN
        ALTER TABLE contacts ALTER COLUMN name TYPE VARCHAR(255);
    END IF;
END $$;

-- Add email column if not exists
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- Add tags column if not exists
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';

-- Add custom_fields column if not exists
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS custom_fields JSONB DEFAULT '{}';

-- Add source column if not exists
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS source VARCHAR(50);

-- Create index for status
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
CREATE INDEX IF NOT EXISTS idx_contacts_first_contact ON contacts(first_contact_at);
