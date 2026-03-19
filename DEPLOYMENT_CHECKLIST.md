# DigitalOcean Deployment Checklist

## Pre-Deployment Checklist

### 1. Security Audit
- [ ] Remove all hardcoded secrets from codebase
- [ ] Use environment variables for all sensitive data
- [ ] Generate a new Django SECRET_KEY for production
- [ ] Review `settings.py` for any hardcoded credentials
- [ ] Ensure DEBUG=False in production
- [ ] Set SECURE_SSL_REDIRECT=True

### 2. Database Setup
- [ ] Create PostgreSQL cluster on DigitalOcean
- [ ] Set database name, user, and password
- [ ] Get connection string from DigitalOcean dashboard
- [ ] Test database connection locally before deployment
- [ ] Configure SSL connection (sslmode=require)
- [ ] Create database backups enabled in DigitalOcean

### 3. Redis Setup
- [ ] Create Redis cluster on DigitalOcean (if using managed service)
- [ ] Get Redis connection string
- [ ] Test Redis connection: `redis-cli -u $REDIS_URL ping`

### 4. Storage Setup (DigitalOcean Spaces)
- [ ] Create a Spaces bucket
- [ ] Generate API keys (Access Key & Secret Key)
- [ ] Choose appropriate region (nearest to users)
- [ ] Get Spaces endpoint URL
- [ ] Configure CORS if needed for file uploads
- [ ] Enable CDN for faster content delivery

### 5. API Keys & Credentials
- [ ] **Iyzico**: Switch from sandbox to production API keys
  - [ ] API Key obtained
  - [ ] Secret Key obtained
  - [ ] Base URL set to https://api.iyzipay.com

- [ ] **Facebook/Instagram**:
  - [ ] App ID obtained
  - [ ] App Secret obtained
  - [ ] Redirect URIs configured in Facebook Developer Console

- [ ] **YouTube**:
  - [ ] Client ID obtained
  - [ ] Client Secret obtained
  - [ ] Oauth consent screen configured
  - [ ] Redirect URI added to Google Cloud Console

- [ ] **OpenAI**:
  - [ ] API Key obtained
  - [ ] API Key has appropriate permissions

- [ ] **RunwayML**:
  - [ ] API Key obtained

- [ ] **Meta Webhooks**:
  - [ ] Verify Token set
  - [ ] Webhook URL configured in Meta App Dashboard

### 6. Email Setup
- [ ] Gmail account created or selected
- [ ] 2-Factor Authentication enabled
- [ ] App-specific password generated
- [ ] Test email sending before deployment

### 7. Code Preparation
- [ ] All dependencies in `requirements.txt`
- [ ] `.env.production` file prepared with all variables
- [ ] `.env` file added to `.gitignore`
- [ ] `DEPLOYMENT_GUIDE.md` reviewed
- [ ] Remove any development-only packages from requirements
- [ ] Update ALLOWED_HOSTS to include production domain

### 8. Django Configuration
- [ ] ALLOWED_HOSTS updated for production domain
- [ ] CSRF_TRUSTED_ORIGINS updated
- [ ] SESSION_COOKIE_DOMAIN set correctly
- [ ] CSRF_COOKIE_DOMAIN set correctly
- [ ] SECURE_SSL_REDIRECT enabled
- [ ] SESSION_COOKIE_SECURE enabled
- [ ] CSRF_COOKIE_SECURE enabled

### 9. Static Files
- [ ] collectstatic command tested locally
- [ ] USE_S3 enabled in production
- [ ] STATICFILES_STORAGE configured for S3
- [ ] Media files configured for S3

### 10. Celery Configuration
- [ ] Redis connection string verified
- [ ] Celery broker URL set correctly
- [ ] Celery result backend set correctly
- [ ] Celery Beat schedule configured
- [ ] Test Celery tasks: `celery -A postless inspect active`

## Deployment Steps

### Step 1: Prepare Environment Variables
```bash
cp .env.example .env.production
# Edit .env.production with all DigitalOcean credentials
# DO NOT commit .env.production to Git
```

### Step 2: Update Django Settings
- [x] Already done - settings.py uses environment variables
- [ ] Verify all environment variables are being read correctly

### Step 3: Push to GitHub
```bash
git add .
git commit -m "Prepare for DigitalOcean deployment"
git push origin main
```

### Step 4: Create DigitalOcean App
1. [ ] Go to DigitalOcean Dashboard → App Platform
2. [ ] Click "Create App"
3. [ ] Connect GitHub repository
4. [ ] Select branch and automatic deployments
5. [ ] Configure build and run commands
6. [ ] Add environment variables (copy from .env.production)
7. [ ] Deploy

### Step 5: Post-Deployment Tasks
```bash
# Run migrations
doctl apps exec YOUR_APP_ID -- python manage.py migrate

# Create superuser
doctl apps exec YOUR_APP_ID -- python manage.py createsuperuser

# Collect static files
doctl apps exec YOUR_APP_ID -- python manage.py collectstatic --noinput

# Test Celery
doctl apps exec YOUR_APP_ID -- celery -A postless inspect active
```

### Step 6: DNS & Domain Configuration
1. [ ] Update DNS records to point to DigitalOcean App Platform
2. [ ] Wait for DNS propagation (5-48 hours)
3. [ ] Test HTTPS connection
4. [ ] Verify SSL certificate is valid

### Step 7: Monitor & Test
1. [ ] Check application logs in DigitalOcean dashboard
2. [ ] Test login functionality
3. [ ] Test payment processing
4. [ ] Test social media integrations
5. [ ] Test email notifications
6. [ ] Monitor Celery workers
7. [ ] Monitor database performance

## Environment Variables Checklist

### Required Variables (Must Set)
- [ ] DJANGO_SECRET_KEY
- [ ] DEBUG=False
- [ ] DATABASE_NAME
- [ ] DATABASE_USER
- [ ] DATABASE_PASSWORD
- [ ] DATABASE_HOST
- [ ] DATABASE_PORT
- [ ] REDIS_URL
- [ ] EMAIL_HOST_USER
- [ ] EMAIL_HOST_PASSWORD

### Optional but Recommended
- [ ] IYZICO_API_KEY (for payments)
- [ ] IYZICO_SECRET_KEY
- [ ] FACEBOOK_APP_ID
- [ ] FACEBOOK_APP_SECRET
- [ ] YOUTUBE_CLIENT_ID
- [ ] YOUTUBE_CLIENT_SECRET
- [ ] OPENAI_API_KEY
- [ ] RUNWAYML_API_KEY
- [ ] BUCKET_ACCESS_KEY (for Spaces)
- [ ] BUCKET_SECRET_KEY
- [ ] BUCKET_NAME
- [ ] BUCKET_REGION
- [ ] BUCKET_ENDPOINT

## Troubleshooting Guide

### Database Connection Issues
**Problem**: "relation 'users_user' does not exist"
**Solution**:
- Ensure migrations have been run: `python manage.py migrate`
- Check database credentials are correct
- Verify database user has proper permissions
- Check DATABASE_HOST, DATABASE_PORT are correct

**Problem**: "permission denied for schema public"
**Solution**:
- Contact DigitalOcean support to grant SCHEMA permissions
- Or use provided SQL commands in Database info panel

### Static Files Not Loading
**Problem**: CSS, images, and JS files not loading
**Solution**:
- Run: `python manage.py collectstatic --noinput --clear`
- Verify Spaces credentials in environment variables
- Check MEDIA_URL points to Spaces endpoint
- Enable CDN in Spaces settings

### Celery Tasks Not Running
**Problem**: Scheduled tasks not executing
**Solution**:
- Verify REDIS_URL is correct: `redis-cli -u $REDIS_URL ping`
- Check Celery worker logs in App Platform dashboard
- Restart Celery workers
- Run: `celery -A postless inspect active`

### Email Not Sending
**Problem**: No confirmation or notification emails received
**Solution**:
- Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
- Check app-specific password was generated (not regular password)
- Test email: `python manage.py shell` → `from django.core.mail import send_mail; send_mail(...)`
- Check spam folder
- Verify firewall allows port 587

### Login Issues
**Problem**: Cannot login or session expires immediately
**Solution**:
- Check SESSION_COOKIE_DOMAIN matches your domain
- Verify CSRF_TRUSTED_ORIGINS includes your domain
- Check ALLOWED_HOSTS includes your domain
- Clear cookies in browser and try again
- Verify database session table exists

## Performance Optimization

- [ ] Enable database query caching
- [ ] Enable Redis caching for sessions
- [ ] Configure CDN for Spaces
- [ ] Set up monitoring and alerts
- [ ] Enable database backups
- [ ] Configure log retention
- [ ] Set up uptime monitoring

## Security Recommendations

- [ ] Enable HTTPS only
- [ ] Set up WAF (Web Application Firewall)
- [ ] Enable VPC for database
- [ ] Rotate API keys monthly
- [ ] Monitor failed login attempts
- [ ] Set up rate limiting
- [ ] Enable database encryption at rest
- [ ] Regular security audits
- [ ] Backup strategy: Daily backups, 30-day retention

## Post-Deployment Support

- Support Email: support@postless.solutions
- Status Page: https://status.postless.solutions
- Documentation: https://docs.postless.solutions
- GitHub Issues: https://github.com/postless/postless/issues

