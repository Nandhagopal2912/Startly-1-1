"""Supabase configuration and database client"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env file")


def get_supabase_client() -> Client:
    """Get Supabase client with anon key (client-side safe)"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_supabase_service_client() -> Client:
    """Get Supabase client with service role key (server-side operations)"""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def init_database():
    """Initialize database tables and schema (Run once)"""
    print("Database schema initialization:")
    print("================================")
    print()
    print("⚠️  IMPORTANT: The Supabase Python client cannot execute DDL statements.")
    print("   You must run the following SQL commands manually in the Supabase dashboard:")
    print()
    print("1. Go to your Supabase project dashboard")
    print("2. Navigate to the SQL Editor")
    print("3. Run the following SQL commands:")
    print()

    # Users table - managed by Supabase Auth, but we'll extend it
    users_table = """
    CREATE TABLE IF NOT EXISTS public.users (
        id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
        email TEXT UNIQUE NOT NULL,
        full_name TEXT,
        avatar_url TEXT,
        company TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    print("Users table SQL:")
    print(users_table)

    # Tasks/Analyses table
    tasks_table = """
    CREATE TABLE IF NOT EXISTS public.tasks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
        keyword TEXT NOT NULL,
        location_name TEXT DEFAULT 'United States',
        search_volume INTEGER,
        ctr_percentage DECIMAL(5, 2),
        zero_click_risk DECIMAL(5, 2),
        commercial_intent DECIMAL(5, 2),
        traffic_opportunity DECIMAL(8, 2),
        verdict TEXT,
        full_results JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    print("Tasks table SQL:")
    print(tasks_table)

    # Create indexes for better performance
    create_indexes = """
    CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON public.tasks(user_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON public.tasks(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON public.tasks(user_id, created_at DESC);
    """
    print("Indexes SQL:")
    print(create_indexes)

    print("4. After creating tables, run setup_rls_policies() to configure security")
    print("   python -c \"from supabase_config import setup_rls_policies; setup_rls_policies()\"")


# Enable Row Level Security (RLS) policies
def setup_rls_policies():
    """Set up Row Level Security policies"""
    print("Row Level Security (RLS) Setup:")
    print("===============================")
    print()
    print("⚠️  IMPORTANT: RLS policies must be created manually in Supabase dashboard.")
    print("   Run these SQL commands in the SQL Editor:")
    print()

    rls_policies = """
    -- Enable RLS on tables
    ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

    -- Users can only see/update their own profile
    CREATE POLICY "Users can view own profile" ON public.users
        FOR SELECT USING (auth.uid() = id);

    CREATE POLICY "Users can update own profile" ON public.users
        FOR UPDATE USING (auth.uid() = id);

    -- Tasks policies - users can only access their own tasks
    CREATE POLICY "Users can view own tasks" ON public.tasks
        FOR SELECT USING (auth.uid() = user_id);

    CREATE POLICY "Users can insert own tasks" ON public.tasks
        FOR INSERT WITH CHECK (auth.uid() = user_id);

    CREATE POLICY "Users can update own tasks" ON public.tasks
        FOR UPDATE USING (auth.uid() = user_id);

    CREATE POLICY "Users can delete own tasks" ON public.tasks
        FOR DELETE USING (auth.uid() = user_id);
    """

    print("RLS Policies SQL:")
    print(rls_policies)
    print()
    print("✅ After running these commands, your database will be properly secured!")
