# Development Deployment Notes

## Azure resources

- Resource Group: `rg-review-robin-web-dev`
- Web App Name: `app-review-robin-web-dev`
- Default Domain: `app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net`
- App Service Plan: `ASP-rgreviewrobinweblab-913a (F1: 1)`
- Operating System: `Linux`
- Runtime Stack: `Python 3.12`

## App startup

Startup command:

```bash
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app
```

## CI/CD workflow

GitHub Actions workflow name:

- `.github/workflows/main_app-review-robin-web-dev.yml`
