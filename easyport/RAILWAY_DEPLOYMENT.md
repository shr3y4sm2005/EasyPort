# EasyPort - Railway Deployment Guide

This guide explains how to deploy EasyPort to Railway, a modern platform for deploying web applications.

## 🚀 Quick Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template-id)

Or follow the manual deployment steps below.

## 📋 Prerequisites

- A [Railway](https://railway.app/) account
- Git repository with your EasyPort code
- Basic understanding of environment variables

## 🔧 Manual Deployment Steps

### 1. Create a New Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click "New Project"
3. Choose "Deploy from GitHub repo"
4. Select your EasyPort repository

### 2. Configure Environment Variables

In your Railway project dashboard, go to the **Variables** tab and set:

**Required Variables:**
```
FLASK_ENV=production
SECRET_KEY=your-super-secure-secret-key-change-this
NOMINATIM_USER_AGENT=easyport/1.0 (contact: your-email@example.com)
```

**Optional Variables:**
```
PROVIDER_API_ENABLED=false
LOG_LEVEL=WARNING
SESSION_COOKIE_SECURE=true
WTF_CSRF_ENABLED=true
```

### 3. Add PostgreSQL Database

1. In your Railway project, click "New Service"
2. Select "Database" → "PostgreSQL"
3. Railway will automatically set the `DATABASE_URL` environment variable

### 4. Deploy

Railway will automatically:
- Detect your Python application
- Install dependencies from `requirements.txt`
- Use the `Procfile` to start your application with Gunicorn
- Assign a public URL to your application

## 🔒 Security Considerations

### Environment Variables
- **Never commit `.env` files** to your repository
- Use Railway's environment variable system for sensitive data
- Generate a strong `SECRET_KEY` for production

### Database Security
- Railway PostgreSQL instances are secured by default
- Use the provided `DATABASE_URL` (automatically configured)
- Enable SSL in production (handled automatically by Railway)

## 📊 Monitoring & Logs

### Application Logs
```bash
# View real-time logs
railway logs

# View logs for specific service
railway logs --service your-service-name
```

### Health Check
Your application includes a health check endpoint:
```
GET /api/health
```

### Metrics
Prometheus metrics are available at:
```
GET /metrics
```

## 🔧 Production Configuration

The application is configured for production with:

- **Gunicorn WSGI server** (4 workers, 120s timeout)
- **ProxyFix middleware** for proper request handling behind Railway's proxy
- **PostgreSQL database** with connection pooling
- **Structured logging** to stdout
- **Rate limiting** with memory or Redis backend
- **CSRF protection** enabled
- **Secure session cookies** in production

## 🚨 Common Issues & Solutions

### Database Connection Issues
```
Error: could not connect to database
```
**Solution:** Ensure PostgreSQL service is added to your Railway project.

### Static Files Not Loading
```
404 errors for CSS/JS files
```
**Solution:** Verify your `static/` directory structure matches the Flask configuration.

### Environment Variables Not Working
```
KeyError: 'SECRET_KEY'
```
**Solution:** Check that all required environment variables are set in Railway dashboard.

### Rate Limiting Issues
```
429 Too Many Requests
```
**Solution:** Adjust rate limits in configuration or add Redis service for distributed rate limiting.

## 📈 Scaling

Railway automatically handles:
- **Horizontal scaling**: Add more instances during high traffic
- **Resource allocation**: CPU and memory scaling
- **Load balancing**: Distribute traffic across instances

To manually scale:
1. Go to your service settings
2. Adjust the "Replicas" setting
3. Monitor performance metrics

## 🔄 CI/CD

Railway automatically redeploys when you push to your connected Git branch. To set up custom deployment:

1. **Connect GitHub**: Link your repository
2. **Auto-deploy**: Enable automatic deployments
3. **Branch protection**: Set deployment branch (e.g., `main`)

## 🌍 Custom Domain

To use a custom domain:

1. Go to your service settings
2. Click "Networking"
3. Add your custom domain
4. Update DNS records as instructed

## 📱 Environment-Specific Settings

### Development
```env
FLASK_ENV=development
LOG_LEVEL=DEBUG
SESSION_COOKIE_SECURE=false
```

### Production
```env
FLASK_ENV=production
LOG_LEVEL=WARNING
SESSION_COOKIE_SECURE=true
```

## 🆘 Support

- **Railway Docs**: [https://docs.railway.app/](https://docs.railway.app/)
- **EasyPort Issues**: [GitHub Issues](https://github.com/your-username/easyport/issues)
- **Railway Discord**: [Join Community](https://discord.gg/railway)

---

## 📝 Post-Deployment Checklist

- [ ] Application starts without errors
- [ ] Health check endpoint responds
- [ ] Database connections work
- [ ] Static files load correctly
- [ ] Authentication flows work
- [ ] API endpoints respond correctly
- [ ] Environment variables are set
- [ ] Logs are properly formatted
- [ ] Rate limiting is functional