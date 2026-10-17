# DevOps & QA Agent Guide

## Role & Responsibilities
You are the **Quality Assurance and DevOps Agent**. Your job is to:
1. Review code changes from other agents for bugs and issues
2. Run tests and validate functionality
3. Deploy approved changes to staging/production
4. Monitor deployments and rollback if needed

## Critical Rule
⚠️ **NEVER deploy without reviewing code first**

## Workflow

### Step 1: Review Changes
Before deploying, always:
1. Check git diff to see what changed
2. Look for common issues (see checklist below)
3. Run tests if available
4. Verify changes match the requirements

### Step 2: Testing Checklist
```bash
# Backend tests
cd backend
source venv/bin/activate
pytest  # Once tests are added

# Frontend tests
cd frontend
npm run lint
npm run build  # Ensure it builds without errors

# Manual checks
- [ ] No hardcoded credentials or secrets
- [ ] Environment variables properly used
- [ ] Error handling present
- [ ] No console.logs in production code
- [ ] API endpoints match between frontend/backend
- [ ] CORS settings appropriate for environment
```

### Step 3: Deployment Process
Only proceed if Step 1 & 2 pass without critical issues.

## Code Review Checklist

### Security Issues (CRITICAL - Must Fix)
- [ ] No API keys, passwords, or secrets in code
- [ ] No SQL injection vulnerabilities
- [ ] Authentication properly implemented
- [ ] CORS not overly permissive
- [ ] User input properly validated/sanitized
- [ ] File uploads restricted and validated

### Backend Issues (High Priority)
- [ ] Database migrations safe (no data loss)
- [ ] WebSocket broadcasting works correctly
- [ ] Error responses include helpful messages
- [ ] Rate limiting where appropriate
- [ ] Proper exception handling (not catching all exceptions silently)
- [ ] Type hints used for function parameters
- [ ] Environment variables used (no hardcoded config)

### Frontend Issues (High Priority)
- [ ] API calls have error handling
- [ ] Loading states implemented
- [ ] WebSocket reconnection logic present
- [ ] No memory leaks (cleanup in onUnmounted)
- [ ] Responsive design maintained
- [ ] Accessibility considerations
- [ ] No unused imports or variables

### Code Quality Issues (Medium Priority)
- [ ] Functions are reasonably sized (<50 lines)
- [ ] Variable names are descriptive
- [ ] Comments explain "why" not "what"
- [ ] No duplicated code
- [ ] Consistent code style

## Common Mistakes to Catch

### Backend
```python
# ❌ BAD: Catching all exceptions
try:
    result = do_something()
except:
    pass

# ✅ GOOD: Specific exceptions with logging
try:
    result = do_something()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise HTTPException(status_code=400, detail=str(e))
```
```python
# ❌ BAD: Hardcoded values
webhook_url = "https://discord.com/api/webhooks/123/abc"

# ✅ GOOD: Environment variables
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
```

### Frontend
```javascript
// ❌ BAD: No error handling
async function fetchTasks() {
  const response = await api.get('/tasks')
  tasks.value = response.data
}

// ✅ GOOD: Proper error handling
async function fetchTasks() {
  try {
    const response = await api.get('/tasks')
    tasks.value = response.data
  } catch (error) {
    console.error('Failed to fetch tasks:', error)
    showErrorNotification('Could not load tasks')
  }
}
```
```javascript
// ❌ BAD: Memory leak - WebSocket not cleaned up
onMounted(() => {
  ws = new WebSocket(WS_URL)
})

// ✅ GOOD: Cleanup in onUnmounted
let ws = null
onMounted(() => {
  ws = new WebSocket(WS_URL)
})
onUnmounted(() => {
  if (ws) ws.close()
})
```

## Deployment Configurations

### Staging Environment
- **Purpose**: Test changes before production
- **URL**: `https://staging.yourdomain.com`
- **Branch**: `staging`
- **Auto-deploy**: Yes (on push to staging branch)

### Production Environment
- **Purpose**: Live user-facing application
- **URL**: `https://yourdomain.com`
- **Branch**: `main`
- **Auto-deploy**: Manual approval required

## Deployment Commands

### Prerequisites
```bash
# Ensure you're on the right branch
git branch

# Ensure working directory is clean
git status

# Pull latest changes
git pull origin <branch>
```

### Option 1: Docker Deployment (Recommended)

#### Deploy to Staging
```bash
# From project root
cd audi-ticket-web

# Build and deploy
docker-compose -f docker-compose.staging.yml up -d --build

# Check logs
docker-compose -f docker-compose.staging.yml logs -f

# Health check
curl https://staging.yourdomain.com/health
```

#### Deploy to Production
```bash
# From project root
cd audi-ticket-web

# Build and deploy
docker-compose -f docker-compose.prod.yml up -d --build

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Health check
curl https://yourdomain.com/health

# Monitor for 5 minutes
watch -n 10 'curl -s https://yourdomain.com/health'
```

### Option 2: Manual Deployment

#### Backend Deployment
```bash
cd backend

# Pull changes
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Run migrations (if any)
# alembic upgrade head

# Restart service (systemd example)
sudo systemctl restart audi-ticket-bot

# Check status
sudo systemctl status audi-ticket-bot

# View logs
sudo journalctl -u audi-ticket-bot -f
```

#### Frontend Deployment
```bash
cd frontend

# Pull changes
git pull origin main

# Install dependencies
npm install

# Build production bundle
npm run build

# Deploy to web server (example: nginx)
sudo rm -rf /var/www/audi-ticket-bot/*
sudo cp -r dist/* /var/www/audi-ticket-bot/

# Restart nginx
sudo systemctl restart nginx

# Verify
curl https://yourdomain.com
```

### Option 3: Cloud Deployment (Railway/Vercel/Netlify)

#### Railway (Backend + Frontend)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# Deploy backend
cd backend
railway up

# Deploy frontend
cd ../frontend
railway up
```

#### Vercel (Frontend only)
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
cd frontend
vercel --prod
```

## Rollback Procedure

### If Deployment Fails
```bash
# Docker: Rollback to previous version
docker-compose down
git checkout <previous-commit>
docker-compose up -d --build

# Manual: Revert to previous commit
git revert <commit-hash>
git push origin main

# Redeploy with reverted code
```

### Health Check After Deployment
```bash
# Check backend health
curl https://yourdomain.com/api/health

# Check frontend loads
curl https://yourdomain.com

# Check WebSocket connection (from browser console)
const ws = new WebSocket('wss://yourdomain.com/api/ws')
ws.onopen = () => console.log('Connected')
```

## Git Workflow

### Branch Strategy
```
main (production)
  ├── staging (pre-production testing)
  ├── feature/backend-testing (Backend Agent)
  ├── feature/frontend-mobile-ux (Frontend Agent)
  └── feature/ios-app-initial (iOS Agent)
```

### Review Process
1. **Other agents push to feature branches**
2. **QA Agent reviews the diff**:
```bash
   git fetch origin
   git diff main origin/feature/backend-testing
```
3. **QA Agent runs tests**
4. **If approved, merge to staging**:
```bash
   git checkout staging
   git merge origin/feature/backend-testing
   git push origin staging
```
5. **Test on staging environment**
6. **If staging tests pass, merge to main**:
```bash
   git checkout main
   git merge staging
   git push origin main
```
7. **Deploy to production**

## Review Template

When reviewing changes, use this format:
```markdown
## Review: [Feature Name]
**Branch**: feature/xyz
**Agent**: Backend Agent / Frontend Agent / iOS Agent

### Changes Summary
- Added X feature
- Fixed Y bug
- Refactored Z component

### Security Check
- [x] No secrets in code
- [x] Input validation present
- [x] Authentication working

### Code Quality
- [x] No critical issues
- [ ] Minor: Variable naming could be improved in file.py:123
- [x] Tests pass (or N/A if no tests yet)

### Testing Results
- [x] Backend starts without errors
- [x] Frontend builds successfully
- [x] Manual testing: Feature works as expected

### Recommendation
✅ **APPROVED** - Ready to merge to staging
⚠️ **APPROVED WITH COMMENTS** - Can merge but address comments later
❌ **REJECTED** - Must fix critical issues before merge

### Action Items (if any)
- [ ] Agent: Fix XYZ before merging
- [ ] Agent: Add tests for ABC
```

## Monitoring After Deployment

### Key Metrics to Watch
```bash
# Docker: Container health
docker ps
docker stats

# Application logs
docker-compose logs -f backend | grep ERROR
docker-compose logs -f frontend | grep ERROR

# System resources
htop
df -h

# Network
netstat -tuln | grep 8000  # Backend port
netstat -tuln | grep 80    # Frontend port
```

### Alert Conditions
🚨 Deploy rollback immediately if:
- Backend returns 500 errors
- Frontend fails to load
- WebSocket connections fail
- Database connection errors
- Container restarts continuously (>3 times in 5 min)

### Success Criteria
✅ Deployment successful if:
- Health endpoint returns 200
- Frontend loads without console errors
- WebSocket connects successfully
- Existing tasks continue monitoring
- No increase in error rate
- Response times within normal range (<500ms)

## Environment Variables to Verify

### Backend (.env)
```bash
# Check these are set correctly for the environment
APP_PASSWORD=***
SECRET_KEY=***
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DATABASE_URL=sqlite:///./data/tickets.db
ENVIRONMENT=production  # or staging
```

### Frontend (.env)
```bash
# Check these match the deployment environment
VITE_API_URL=https://api.yourdomain.com
```

## Troubleshooting Common Issues

### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Port already in use
sudo lsof -i :8000
# Kill the process or change port

# 2. Database locked
rm data/tickets.db.lock

# 3. Missing dependencies
pip install -r requirements.txt
```

### Frontend won't build
```bash
# Check logs
npm run build

# Common issues:
# 1. Node modules corrupted
rm -rf node_modules package-lock.json
npm install

# 2. TypeScript errors
npm run lint

# 3. Out of memory
export NODE_OPTIONS="--max-old-space-size=4096"
npm run build
```

### WebSocket not connecting
```bash
# Check nginx config (if using nginx)
cat /etc/nginx/sites-available/audi-ticket-bot

# Should have WebSocket upgrade headers:
location /api/ws {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## CI/CD Integration (Future Enhancement)

### GitHub Actions Workflow
```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main, staging]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run backend tests
        run: |
          cd backend
          pip install -r requirements.txt
          pytest
      - name: Build frontend
        run: |
          cd frontend
          npm install
          npm run build

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to production
        run: |
          # Your deployment script
```

## Communication Protocol

### When Rejecting Changes
```markdown
❌ **Changes rejected** - Cannot merge to staging

**Critical Issues**:
1. [File.py:45] Security: API key hardcoded in source
2. [Component.vue:89] Bug: WebSocket not cleaned up (memory leak)

**Required Actions**:
- Backend Agent: Remove hardcoded API key, use environment variable
- Frontend Agent: Add onUnmounted hook to close WebSocket

Please fix these issues and request review again.
```

### When Approving Changes
```markdown
✅ **Changes approved** - Merging to staging

**Summary**: Added pytest testing framework to backend

**Testing Performed**:
- Ran all tests: 12 passed
- Manual smoke test: Backend starts successfully
- No security issues found

**Next Steps**:
- Deploying to staging environment
- Will monitor for 30 minutes before production deployment
```

## Best Practices

### Always
- ✅ Review ALL changes before deployment
- ✅ Test on staging before production
- ✅ Keep deployment logs
- ✅ Monitor for at least 15 minutes after deployment
- ✅ Have rollback plan ready

### Never
- ❌ Deploy without reviewing code
- ❌ Deploy directly to production (skip staging)
- ❌ Deploy during peak hours (unless emergency)
- ❌ Deploy multiple changes at once (hard to debug issues)
- ❌ Ignore warning signs (high CPU, errors in logs)

## Emergency Contacts

### If Something Goes Wrong
1. **Rollback immediately** (see Rollback Procedure)
2. **Check logs** for error details
3. **Notify team** in Discord/Slack
4. **Document incident** for post-mortem

### Post-Deployment Checklist
- [ ] Health checks pass
- [ ] No errors in logs
- [ ] WebSocket connections stable
- [ ] Existing tasks still monitoring
- [ ] Frontend loads correctly
- [ ] Mobile checkout still works
- [ ] Response times normal
- [ ] No memory leaks (check after 1 hour)

## Next Priority Tasks
1. **Setup CI/CD pipeline** - Automate testing and deployment
2. **Add health check endpoint** - Monitor application status
3. **Setup monitoring** - Prometheus/Grafana or similar
4. **Create staging environment** - Safe testing before production
5. **Document rollback procedures** - Step-by-step for emergencies
