import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://snaqzbibxafbqxlxusdi.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNuYXF6YmlieGFmYnF4bHh1c2RpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc1MTA2NDAsImV4cCI6MjA4MzA4NjY0MH0.gOWKhIbPTPr9qJo7xN9qN696EovHQb7t3-uFYZlAuRw';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export default supabase;
