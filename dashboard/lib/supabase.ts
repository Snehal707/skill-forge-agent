import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // eslint-disable-next-line no-console
  console.warn(
    "[Skill Forge] NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY is not set.",
  );
}

export type EventRow = {
  id: string;
  event_type: string;
  domain: string | null;
  skill_name: string | null;
  message: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

export type SkillRow = {
  id: string;
  name: string;
  domain: string;
  category: string;
  description: string | null;
  content: string;
  validation_passed: boolean;
  sources_count: number | null;
  attempts: number | null;
  created_at: string;
};

export const supabase: SupabaseClient | null =
  supabaseUrl && supabaseAnonKey
    ? createClient(supabaseUrl, supabaseAnonKey)
    : null;

