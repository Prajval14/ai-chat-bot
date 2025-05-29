## Getting Started

1. Fork and clone this repo.
2. Copy `.env.sample` from /src/api to `.env` and fill in your OpenAI/Neo4j keys.
3. (Optional but recommended) Run `python scripts/predeploy.py` to validate your setup.
4. Run `azd login` and select your Azure subscription.
5. Run `azd up` to deploy everything. The script will prompt you if Neo4j credentials are missing.
6. On completion, the terminal will display your API and Web URLs.

*Note: For production, set secrets as App Service or Static Web App configuration settings in Azure Portal or via CLI.*