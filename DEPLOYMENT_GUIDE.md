# DigitalOcean Deployment Setup Guide

## Overview
This guide will help you set up all the necessary environment variables for deploying your Postless application on DigitalOcean.

## Prerequisites
- DigitalOcean Account
- PostgreSQL Database (Managed Database)
- Redis (Managed Database or Upstash)
- DigitalOcean Spaces (for S3-compatible storage)
- App Platform (for deploying the application)

## Environment Variables Setup

### 1. Django Core Settings
```
DEBUG=False
DJANGO_SECRET_KEY=your-secret-key-here-change-this-in-production
```

Generate a secure SECRET_KEY:
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### 2. PostgreSQL Database Configuration
Get these from your DigitalOcean Managed Database dashboard:

```
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=db
DATABASE_USER=db
DATABASE_PASSWORD=your-database-password
DATABASE_HOST=app-XXXXX-do-user-XXXXX-0.k.db.ondigitalocean.com
DATABASE_PORT=25060
```

**Steps to find these:**
1. Go to DigitalOcean Dashboard → Databases
2. Select your PostgreSQL cluster
3. Click on "Connection Details" → "Connection string"
4. Extract the credentials from the connection string

### 3. Redis Configuration
For Celery and session management:

```
REDIS_URL=redis://default:your-redis-password@your-redis-host:25061/0
```

**Steps:**
1. Go to DigitalOcean Dashboard → Databases
2. Select your Redis cluster
3. Copy the connection string
4. Format: `redis://username:password@host:port/0`

### 4. DigitalOcean Spaces (S3-Compatible Storage)

```
USE_S3=TRUE
BUCKET_NAME=your-bucket-name
BUCKET_ACCESS_KEY=your-spaces-access-key
BUCKET_SECRET_KEY=your-spaces-secret-key
BUCKET_REGION=nyc3  # or use sfo3, sgp1, ams3, fra1
BUCKET_ENDPOINT=https://nyc3.digitaloceanspaces.com
```

**Steps:**
1. Go to DigitalOcean Dashboard → Spaces
2. Create a new Space
3. Go to Settings → API Tokens
4. Generate or copy your Space Access Key and Secret Key
5. Choose the region closest to your users

### 5. Payment Gateway (Iyzico)
For production, switch from sandbox to live:

```
IYZICO_API_KEY=your-live-api-key
IYZICO_SECRET_KEY=your-live-secret-key
IYZICO_BASE_URL=https://api.iyzipay.com
```

Get these from: https://merchant.iyzipay.com/

### 6. Social Media Integration

#### Facebook / Instagram
```
FACEBOOK_APP_ID=your-facebook-app-id
FACEBOOK_APP_SECRET=your-facebook-app-secret
```

Get from: https://developers.facebook.com/apps/

#### Instagram (Meta)
```
INSTAGRAM_APP_ID=your-instagram-app-id
INSTAGRAM_CLIENT_SECRET=your-instagram-client-secret
INSTAGRAM_ACCESS_TOKEN=your-long-lived-access-token
INSTAGRAM_ACCOUNT_ID=your-instagram-business-account-id
META_WEBHOOK_VERIFY_TOKEN=your-unique-verify-token
```

Get from: https://business.facebook.com/

#### YouTube
```
YOUTUBE_CLIENT_ID=your-youtube-client-id
YOUTUBE_CLIENT_SECRET=your-youtube-client-secret
```

Get from: https://console.cloud.google.com/

### 7. AI Services

```
OPENAI_API_KEY=your-openai-api-key
RUNWAYML_API_KEY=your-runwayml-api-key
```

Get from:
- OpenAI: https://platform.openai.com/api-keys
- RunwayML: https://app.runwayml.com/settings/api-keys

### 8. Email Configuration (Gmail SMTP)

```
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password
```

**Steps to generate App Password:**
1. Go to https://myaccount.google.com/security
2. Enable 2-Factor Authentication
3. Scroll to "App passwords"
4. Select "Mail" and "Windows Computer" (or your app)
5. Generate the 16-character password
6. Use this password in EMAIL_HOST_PASSWORD

## DigitalOcean App Platform Setup

### 1. Connect Your Repository
1. Go to DigitalOcean Dashboard → App Platform
2. Click "Create App"
3. Connect your GitHub repository
4. Select your branch (main/production)

### 2. Configure Environment Variables
1. Click on your app
2. Go to "Settings" → "Environment"
3. Add all the variables from your `.env.production` file
4. Or upload the entire `.env.production` file

### 3. Build Configuration
Create a `app.yaml` file in your repository root:

```yaml
name: postless
services:
- name: web
  github:
    repo: YOUR_GITHUB_ORG/postless
    branch: main
  build_command: pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
  run_command: gunicorn postless.wsgi:application --bind 0.0.0.0:8080
  envs:
  - key: DEBUG
    value: "False"
  http_port: 8080
  health_check:
    http_path: /health/
  http_routes:
  - path: /
    preserve_path_prefix: true

- name: celery
  github:
    repo: YOUR_GITHUB_ORG/postless
    branch: main
  build_command: pip install -r requirements.txt
  run_command: celery -A postless worker -l info
  envs:
  - key: DEBUG
    value: "False"

- name: celery-beat
  github:
    repo: YOUR_GITHUB_ORG/postless
    branch: main
  build_command: pip install -r requirements.txt
  run_command: celery -A postless beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
  envs:
  - key: DEBUG
    value: "False"

static_sites:
- name: cdn
  source_dir: staticfiles

databases:
- name: postgresql-db
  engine: PG
  version: "14"
  production: true

- name: redis-cache
  engine: REDIS
  version: "7"
  production: true
```

### 4. Deploy
1. Click "Deploy" button
2. Monitor the build process
3. Once deployed, update your DNS records to point to the DigitalOcean App Platform URL

## Post-Deployment Tasks

### 1. Run Migrations
After deployment, run:
```bash
python manage.py migrate
python manage.py createsuperuser
```

Via SSH:
```bash
doctl apps exec YOUR_APP_ID -- python manage.py migrate
doctl apps exec YOUR_APP_ID -- python manage.py createsuperuser
```

### 2. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 3. Update DNS Records
1. Go to DigitalOcean Dashboard → Networking → Domains
2. Add CNAME record pointing to your App Platform URL

## Security Recommendations

1. **Never commit `.env` files to Git** - Add to `.gitignore`
2. **Use strong SECRET_KEY** - Generate new one for production
3. **Enable HTTPS** - DigitalOcean handles this automatically
4. **Rotate API Keys regularly** - Especially payment gateway keys
5. **Use environment-specific credentials** - Never use development keys in production
6. **Enable database backups** - DigitalOcean Managed Databases support automated backups
7. **Set up monitoring and alerts** - Use DigitalOcean monitoring tools

## Troubleshooting

### Database Connection Issues
```bash
# Test PostgreSQL connection
python manage.py dbshell

# Run migrations
python manage.py migrate

# If permission denied:
# Contact DigitalOcean support to grant proper database privileges
```

### Static Files Not Loading
```bash
# Re-collect static files
python manage.py collectstatic --noinput --clear

# Verify Spaces configuration
python manage.py shell
>>> from django.conf import settings
>>> print(settings.MEDIA_URL)
```

### Celery Tasks Not Running
```bash
# Check Celery logs
# Via DigitalOcean App Platform dashboard → Logs

# Verify Redis connection
redis-cli -u $REDIS_URL ping

# Check Celery worker status
celery -A postless inspect active
```

## References

- [DigitalOcean PostgreSQL Documentation](https://docs.digitalocean.com/products/databases/postgresql/)
- [DigitalOcean Redis Documentation](https://docs.digitalocean.com/products/databases/redis/)
- [DigitalOcean Spaces Documentation](https://docs.digitalocean.com/products/spaces/)
- [DigitalOcean App Platform Documentation](https://docs.digitalocean.com/products/app-platform/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/)

