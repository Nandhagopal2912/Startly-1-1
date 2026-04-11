# Startly Complete Setup Guide

Complete guide to set up Supabase, OAuth, Redis, and all components for the Startly application.

## 📋 Table of Contents

1. [Supabase Setup](#supabase-setup)
2. [OAuth Configuration](#oauth-configuration)
3. [Redis Setup](#redis-setup)
4. [Backend Configuration](#backend-configuration)
5. [Frontend Configuration](#frontend-configuration)
6. [Database Initialization](#database-initialization)
7. [Running the Application](#running-the-application)

## 🔧 Supabase Setup

### Step 1: Create Supabase Project

1. Go to [Supabase Console](https://app.supabase.com)
2. Click "New Project"
3. Fill in the details:
   - Organization: (select or create)
   - Project Name: `startly-prod` or similar
   - Database Password: (generate strong password)
   - Region: Select closest to you
4. Click "Create New Project" and wait for completion

### Step 2: Get Your Credentials

Once the project is created:

1. Go to **Settings → API Keys**
2. Copy the following:
   - **Project URL**: Copy this (format: `https://xxxxx.supabase.co`)
   - **anon public key**: This goes to `SUPABASE_ANON_KEY`
   - **service_role secret**: This goes to `SUPABASE_SERVICE_ROLE_KEY`

### Step 3: Create Database Tables

1. Go to **SQL Editor** in Supabase Console
2. Create a new query and paste:

```sql
-- Users table (extended profile)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    company TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks/Analyses table
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

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON public.tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON public.tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON public.tasks(user_id, created_at DESC);

-- Enable Row Level Security
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

-- RLS Policies for Users
CREATE POLICY "Users can view their own profile"
  ON public.users FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile"
  ON public.users FOR UPDATE
  USING (auth.uid() = id);

-- RLS Policies for Tasks
CREATE POLICY "Users can view their own tasks"
  ON public.tasks FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own tasks"
  ON public.tasks FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own tasks"
  ON public.tasks FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own tasks"
  ON public.tasks FOR DELETE
  USING (auth.uid() = user_id);
```

3. Click "Run" and verify tables are created

## 🔐 OAuth Configuration

### Step 1: Enable OAuth Providers

In Supabase Console:

1. Go to **Authentication → Providers**

#### Google OAuth

1. Click on **Google**
2. Set **Enabled** to ON
3. Go to [Google Cloud Console](https://console.cloud.google.com)
4. Create a new project or select existing
5. Enable **Google+ API**
6. Go to **Credentials → Create Credentials → OAuth 2.0 Client ID**
7. Choose **Web application**
8. Add authorized redirect URIs:
   - `https://your-project.supabase.co/auth/v1/callback?provider=google`
   - `http://localhost:3000/auth/callback`
9. Copy **Client ID** and **Client Secret** into Supabase Google provider settings
10. Click **Save**

#### GitHub OAuth

1. Go to GitHub → Settings → Developer settings → OAuth Apps
2. Click **New OAuth App**
3. Fill in:
   - Application name: `Startly`
   - Homepage URL: `http://localhost:3000` (or your domain)
   - Authorization callback URL: `https://your-project.supabase.co/auth/v1/callback?provider=github`
4. Copy **Client ID** and **Client Secret**
5. In Supabase, enable GitHub provider and paste credentials
6. Click **Save**

#### Microsoft OAuth

1. Go to [Azure Portal](https://portal.azure.com)
2. Register a new application in **App registrations**
3. Create a client secret
4. Add redirect URIs:
   - `https://your-project.supabase.co/auth/v1/callback?provider=azure`
   - `http://localhost:3000/auth/callback`
5. Copy **Client ID** and **Client Secret**
6. In Supabase, enable Microsoft provider and paste credentials
7. Click **Save**

### Step 2: Configure Supabase Auth Settings

1. Go to **Authentication → URL Configuration**
2. Set **Site URL** to your frontend URL:
   - Development: `http://localhost:3000`
   - Production: Your domain
3. Add **Redirect URLs** (comma-separated):
   ```
   http://localhost:3000/auth/callback,
   http://localhost:3000/dashboard,
   http://localhost:3000/login
   ```
4. Click **Save**

## 💾 Upstash Redis Setup

### Recommended: Upstash (Easiest - No Local Installation)

1. Go to [Upstash Console](https://console.upstash.com/)
2. Create a free account
3. Click "Create Database"
4. Choose "Redis" as the database type
5. Select your region (choose closest to you)
6. Click "Create"
7. Copy the **Redis URL** from the database details (starts with `rediss://`)
8. Use this as `REDIS_URL` in your `.env` file

**Free tier**: 10,000 requests/month, perfect for development!

### Alternative: Local Redis (Development Only)

```bash
# Windows - Using WSL or Docker
docker run -d -p 6379:6379 redis:latest

# Or install Redis directly on Windows from: https://github.com/microsoftarchive/redis/releases
```

### Alternative: Redis Cloud (Production)

1. Go to [Redis Cloud](https://redis.com/try-free/)
2. Create a free account
3. Create a new database
4. Copy the connection URL (format: `redis://:password@host:port`)
5. Use this as `REDIS_URL` in `.env`

### Option 3: Docker Compose

Create `docker-compose.yml` at project root:

```yaml
version: "3.8"

services:
  redis:
    image: redis:latest
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  redis_data:
```

Run: `docker-compose up -d`

## 🚀 Backend Configuration

### Step 1: Install Dependencies

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Step 2: Create `.env` File

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# DataForSEO
DATAFORSEO_EMAIL=your_email@example.com
DATAFORSEO_PASSWORD=your_api_password

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Upstash Redis
REDIS_URL=rediss://username:password@host:port

# Frontend
FRONTEND_URL=http://localhost:3000
```

### Step 3: Test Backend

```bash
python -m uvicorn main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` to see API documentation.

## 🎨 Frontend Configuration

### Step 1: Install Dependencies

```bash
cd frontend
npm install
```

### Step 2: Create `.env.local` File

```bash
cp .env.example .env.local
```

Edit `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_FRONTEND_URL=http://localhost:3000
```

### Step 3: Check File Structure

Ensure these files exist:

- `app/login/page.tsx` - Login page
- `app/auth/callback/page.tsx` - OAuth callback handler
- `app/activities/page.tsx` - Activity history
- `contexts/AuthContext.tsx` - Auth context provider

## 🗄️ Database Initialization

### Automatic Setup

The backend includes database initialization. Run:

```bash
cd backend
python -c "from supabase_config import init_database; init_database()"
```

### Manual Setup

Use the SQL commands provided in the Supabase Setup section.

## ▶️ Running the Application

### Terminal 1: Backend

```bash
cd backend
source venv/bin/activate  # venv\Scripts\activate on Windows
python -m uvicorn main:app --reload --port 8000
```

Backend will be available at: `http://localhost:8000`
API Docs: `http://localhost:8000/docs`

### Terminal 2: Redis

```bash
redis-server
# OR if using Docker:
docker-compose up
```

### Terminal 3: Frontend

```bash
cd frontend
npm run dev
```

Frontend will be available at: `http://localhost:3000`

## ✅ Testing the Setup

1. **Test Backend Health**

   ```bash
   curl http://localhost:8000/health
   ```

2. **Test Redis Connection**
   - Backend logs should show: "✓ Redis connection successful"

3. **Access Frontend**
   - Open http://localhost:3000
   - Click "Sign in with Google/GitHub/Microsoft"
   - You should be redirected to OAuth provider
   - After authentication, redirected to dashboard

4. **Test API Endpoints**
   - Visit http://localhost:8000/docs (Swagger UI)
   - Try auth endpoints with your token

## 🔑 API Endpoints

### Authentication

- `POST /auth/callback` - OAuth callback handler
- `GET /auth/me` - Get current user
- `GET /auth/providers` - Get available OAuth providers
- `GET /auth/logout` - Logout user

### Tasks/Analyses

- `POST /tasks` - Create new analysis
- `GET /tasks` - List user's tasks
- `GET /tasks/{task_id}` - Get specific task
- `DELETE /tasks/{task_id}` - Delete task
- `GET /tasks/{task_id}/download` - Download report

### Statistics

- `GET /stats` - Get user statistics
- `GET /search?keyword=...` - Search tasks

### Original Endpoints

- `POST /analyze` - SEO analysis
- `POST /report` - Generate report (CSV/PDF)

## 🐛 Troubleshooting

### Redis Connection Failed

- Ensure Redis is running: `redis-cli ping` should return `PONG`
- Check `REDIS_URL` in `.env`

### Supabase Connection Failed

- Verify `SUPABASE_URL` and keys in `.env`
- Check internet connection
- Test: `curl https://your-project.supabase.co`

### OAuth Not Working

- Verify redirect URIs in OAuth provider settings
- Check `FRONTEND_URL` matches your setup
- Ensure cookies are enabled in browser

### CORS Errors

- Backend CORS is set to allow all origins (\*)
- For production, change in `main.py`:
  ```python
  allow_origins=["https://yourdomain.com"]
  ```

## 📚 Additional Resources

- [Supabase Docs](https://supabase.com/docs)
- [Redis Docs](https://redis.io/docs/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Next.js Docs](https://nextjs.org/docs)
