# 目录结构说明（用于 epigenetic-agent 项目初始化）

# 项目根目录结构

|____start_code
|____environment.yml
|____epigenicai_app
| |____migrations
| | |______init__.py
| |____models.py
| |______init__.py
| |____apps.py
| |____admin.py
| |____templates
| | |____index.html
| | |____results.html
| |____tests.py
| |____urls.py
| |____views.py
|____django_project
| |____asgi.py
| |____settings.py
| |____urls.py
| |____wsgi.py
|____db.sqlite3
|____dir.md
|____agent_core
| |____clients
| | |____llm_client.py
| |____tools
| | |____web_scraper.py
| | |______init__.py
| | |____rag
| | | |____vector_db.py
| | | |____embedder.py
| | | |____rag_orchestrator.py
| | |____pubmed_search.py
| |____work_flow.md
| |____requirements.txt
| |____state_machine
| | |______init__.py
| | |____graph_definition.py
| | |____graph_runner.py
| |____config.yaml
| |____agents
| | |____report_agent.py
| | |____control_agent.py
| | |____commercial_agent.py
| | |____literature_agent.py
| | |______init__.py
| | |____citation_auditor.py
| | |____completeness_auditor.py
| | |____web_agent.py
| | |____literature_agent
| | | |____runner.py
| | | |____retriever
| | | | |____pubmed_retriever.py
| | | |____prompts.py
| |____agent_env.yml
| |____readme.md
| |____prompts
| | |____control_agent_prompts.py
| | |____formatting_utils.py
| |____report
| | |____formatter.py
| | |____markdown_to_ppt.py
| | |______init__.py
| | |____markdown_to_word.py
| | |____writer.py
|____manage.py