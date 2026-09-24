# AstroAI — Topic-Agnostic Astrology Workflow (Django + LangChain + LangGraph + AstrologyAPI)

AstroAI is a robust, topic-agnostic astrology API that answers any life question (career, marriage, relationships, health, wealth, education, travel, litigation, spirituality, family, property, foreign, etc.) using:
- **Django + DRF** for the API
- **LangChain** for LLM orchestration and tools
- **LangGraph** for multi-step control flow
- **AstrologyAPI** for charts, planetary data, dashas, etc.
- **OpenAI** for structured reasoning and client-ready memos

## Features
- Topic-agnostic: handles any question, not just pre-defined domains
- Extensible ontology: add new topics, synonyms, house mappings easily
- Modular chains: intent detection, foundational read, house analysis, timing, synthesis, memo
- Universal AstrologyAPI integration: always fetches all relevant data for maximal context
- Caching-ready: add caching to reduce API costs
- Modern, maintainable codebase

## Project Layout
```
astroai/
├─ manage.py
├─ requirements.txt
├─ .env.example
├─ astroai/
│  ├─ settings.py
│  ├─ urls.py
│  └─ wsgi.py
└─ astro/
   ├─ __init__.py
   ├─ apps.py
   ├─ urls.py
   ├─ views.py
   ├─ models.py
   ├─ admin.py
   ├─ serializers.py
   ├─ schemas.py
   ├─ ontology.py
   ├─ services/
   │  ├─ astrologyapi.py
   │  ├─ tools.py
   │  ├─ chains.py
   │  ├─ graph.py
   │  └─ storage.py
   └─ tests/
      └─ test_endpoints.py
```

## Environment Setup
Copy `.env.example` to `.env` and fill in your keys:
```
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=*
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ASTROLOGYAPI_BASE_URL=https://api.astrologyapi.com/v1
ASTROLOGYAPI_USER_ID=your_user_id
ASTROLOGYAPI_API_KEY=your_api_key
ASTROLOGYAPI_LANG=en
```

## Quickstart
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run migrations:
   ```bash
   python manage.py migrate
   ```
3. Start the server:
   ```bash
   python manage.py runserver
   ```
4. Test the API:
   ```bash
   curl -X POST http://localhost:8000/api/workflow/run/ \
     -H 'Content-Type: application/json' \
     -d '{"question": "What are my next 12 months looking like overall?", "client": {"name": "Asha", "dob": "1990-05-10", "birth_time": "19:55", "birthplace": "Jaipur, India", "latitude": 26.9124, "longitude": 75.7873, "timezone": 5.5}}'
   ```

## Extending
- Add new topics/synonyms in `astro/ontology.py`
- Add new chains or tools in `astro/services/`
- Add caching in `astro/services/storage.py`

## License
MIT
