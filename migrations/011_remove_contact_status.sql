-- =====================================================
-- WhatsApp CRM - Remove Contact Status
-- Remove status field from contacts table
-- =====================================================

-- Remove status column and index from contacts table
DROP INDEX IF EXISTS idx_contacts_status;
ALTER TABLE contacts DROP COLUMN IF EXISTS status;
