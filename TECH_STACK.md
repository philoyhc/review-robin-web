# Technology Stack

Review Robin Web uses the following baseline stack:

- Azure App Service for Linux
- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy 2.x + Alembic, when database work begins
- Azure Database for PostgreSQL Flexible Server
- Jinja2 templates
- HTMX for targeted interactivity
- AG Grid or equivalent for reviewer tables
- Azure App Service Easy Auth with Microsoft Entra ID
- Azure Storage Queue + Azure Functions for bulk jobs
- Institutional SMTP relay, with Azure Communication Services Email as fallback
- Azure Blob Storage for uploads and exports
- Application Insights / Azure Monitor
- pytest + FastAPI TestClient
- GitHub Actions CI/CD
