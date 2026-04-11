# 🚀 Quick Start Guide

Get Startly fully operational in 5 steps.

## ⚡ 5-Minute Setup (Development)

### Step 1: Clone & Install (2 min)

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# OR: source venv/bin/activate  # Mac/Linux
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### Step 2: Configure Environment (2 min)

```bash
# Backend
cd backend
cp .env.example .env
# Edit .env with your credentials (see config below)

# Frontend
cd ../frontend
cp .env.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Step 3: Quick Configuration

**Minimum Required:**

1. **Supabase** (Free tier: https://app.supabase.com)
   - Create project
   - Get: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   - Run SQL from SETUP_GUIDE.md

2. **Upstash Redis** (Free tier: https://upstash.com)
   - Create free account
   - Create a Redis database
   - Copy the Redis URL (starts with `rediss://`)
   - No local installation needed!

3. **OAuth** (Pick one or all)
   - Google: easiest setup, enable in Supabase Auth
   - GitHub: register app at https://github.com/settings/developers
   - Microsoft: register app at https://azure.microsoft.com

### Step 4: Start Services (Open 3 terminals)

```bash
# Terminal 1: Backend
cd backend && python -m uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

### Step 5: Use It! (30 sec)

1. Open http://localhost:3000
2. Click "Sign in with [Provider]"
3. Complete OAuth flow
4. You're in the dashboard! 🎉

---

## 📋 Configuration Reference

### Minimum `.env` (Backend)

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=your_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_key

# Upstash Redis
REDIS_URL=rediss://username:password@host:port

# DataForSEO (use existing credentials)
DATAFORSEO_EMAIL=your_email@example.com
DATAFORSEO_PASSWORD=your_password

# Frontend
FRONTEND_URL=http://localhost:3000
```

### Minimum `.env.local` (Frontend)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_FRONTEND_URL=http://localhost:3000
```

---

## ✅ Verify Setup

```bash
# Check backend
curl http://localhost:8000/health
# Should return: {"status":"ok"}

# Check API docs
open http://localhost:8000/docs

# Check frontend
open http://localhost:3000
```

---

## 🆘 Common Issues

### "Redis connection failed"

- Verify your Upstash Redis URL is correct
- Check that your Upstash database is active
- Ensure the URL starts with `rediss://` (SSL required)

### "Supabase credentials error"

- Verify copied keys are complete (no truncation)
- Check URL doesn't have trailing slash
- Ensure database tables were created (run SQL)

### "OAuth redirect failed"

- Check redirect URI in OAuth provider settings
- Verify FRONTEND_URL is correct
- Clear browser cookies/cache

### Port 8000 already in use

```bash
uvicorn main:app --port 8001
```

### Port 3000 already in use

```bash
npm run dev -- -p 3001
```

---

## 📚 Full Documentation

- **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** - Detailed setup (with screenshots)
- **[IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)** - Technical details
- **[README.md](./README.md)** - Original feature documentation

---

## 🎯 What's New

✨ **User Accounts** - Sign in with Google/GitHub/Microsoft  
📊 **Activity History** - See all past analyses  
💾 **Database Storage** - All data persisted in Supabase  
⚡ **Redis Cache** - Faster repeated searches  
📥 **Download Reports** - Export as PDF or CSV

---

## 🆓 Free Tier Limits

- **Supabase**: 500MB storage, unlimited API calls
- **Upstash Redis**: 10,000 requests/month free
- **GitHub OAuth**: Unlimited
- **Google OAuth**: 10k req/day (dev mode)

---

## 📖 API Examples

### Create Analysis & Save

```bash
# Sign in (get token)
curl -X POST http://localhost:8000/auth/callback \
  -H "Content-Type: application/json" \
  -d '{"provider":"google","code":"auth_code"}'

# Get your profile
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create task
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "best seo tools",
    "location_name": "United States",
    "search_volume": 5000,
    "traffic_opportunity": 75.5
  }'

# View all tasks
curl http://localhost:8000/tasks \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🚢 Deploy to Production

### Backend (Heroku, Railway, etc)

```bash
# Set environment variables in platform
# Deploy with git

heroku create startly-prod
git push heroku main
```

### Frontend (Vercel)

```bash
npm install -g vercel
vercel

# Set NEXT_PUBLIC_API_URL to production backend
```

---

## 💡 Tips

1. **Save your OAuth credentials** - You'll need them
2. **Use `.env` for secrets**, never commit to git
3. **Upstash Redis is ready to use** - No local setup needed
4. **Enable RLS in Supabase** - Already included in schema
5. **Check API docs** at `/docs` for all endpoints

---

## 🎉 You're Done!

Your full-stack SEO tool with authentication and history is ready!

Next: Customize colors, add your branding, deploy to production.

Questions? Check SETUP_GUIDE.md or API docs at /docs
