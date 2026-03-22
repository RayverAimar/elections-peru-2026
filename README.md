# Peru Elecciones 2026 - Vote Compass

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?logo=fastapi&logoColor=white)
![Astro](https://img.shields.io/badge/Astro-6.0-BC52EE?logo=astro&logoColor=white)
![Preact](https://img.shields.io/badge/Preact-10.x-673AB8?logo=preact&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-4169E1?logo=postgresql&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?logo=tailwindcss&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Haiku_%2B_Sonnet-D97706?logo=anthropic&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

Plataforma electoral para las elecciones generales del Perú 2026 (12 de abril). Combina una brújula electoral (quiz adaptativo), un chatbot RAG sobre planes de gobierno, monitoreo de noticias, y seguimiento de eventos políticos.

<p align="center">
  <img src="docs/screenshot.png" alt="Chasqui — Tu mensajero electoral" width="720" />
</p>

## Requisitos

- Python 3.13+
- Node.js 22+
- Docker
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes Python)

## Instalación

```bash
git clone <repo-url>
cd peru-elecciones-2026

# 1. Configurar variables de entorno
cp .env.example .env
# Editar .env y agregar tu ANTHROPIC_API_KEY

# 2. Setup completo (Docker + dependencias + migraciones + frontend)
make setup
```

Esto ejecuta:
- `docker compose up -d` — PostgreSQL 16 + pgvector en puerto 5434
- `uv sync` — Instala dependencias Python
- `uv run pre-commit install` — Configura el hook de pre-commit (ruff)
- `python scripts/migrate.py` — Crea el schema de la base de datos
- `cd web && npm install && npm run build` — Construye el frontend

## Uso

```bash
# Iniciar el servidor API (con hot-reload)
make dev
# → http://localhost:8000

# En otra terminal, iniciar el frontend en modo desarrollo
make dev-frontend
# → http://localhost:4321
```

## Pipeline de datos

Los datos ya están incluidos en el repositorio (`data/`). Si necesitas regenerarlos desde cero:

```bash
# Pipeline completo (3 pasos automáticos)
make pipeline                         # Solo presidenciales (default)
make pipeline SCOPE=formula           # Fórmula completa (108 candidatos)
make pipeline SCOPE=all               # Todas las elecciones

# O paso a paso:
make fetch-candidates                 # Candidatos presidenciales
make fetch-candidates SCOPE=all       # Todas las elecciones
make collect-content                  # Planes + noticias + eventos (presidenciales)
make collect-content SCOPE=formula    # Planes + noticias + eventos (fórmula completa)
make extract-positions                # Extraer posiciones con LLM (consume créditos API)
```

## Estructura del proyecto

```
├── app/                    Aplicación FastAPI
│   ├── models/             Modelos Pydantic (candidates, quiz, news, events, investigation)
│   ├── routers/            Endpoints REST (candidates, quiz, chat, news, events, investigation)
│   └── services/           Lógica de negocio (RAG, quiz adaptativo, datos)
├── data/                   Datos estáticos (JSON + PDFs)
├── migrations/             Migraciones SQL numeradas
├── scripts/                Pipeline de datos (one-time)
├── web/                    Frontend (Astro + Preact + Tailwind)
└── Makefile                Comandos de desarrollo
```

## API Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/candidates` | GET | Lista todos los partidos |
| `/candidates/{id}` | GET | Detalle de un partido |
| `/quiz/start` | POST | Inicia el quiz adaptativo |
| `/quiz/answer` | POST | Envía una respuesta, retorna siguiente pregunta |
| `/quiz/results` | POST | Calcula matches finales |
| `/quiz/explain` | POST | Explica el match con un partido específico |
| `/chat` | POST | Pregunta al chatbot RAG |
| `/noticias` | GET | Lista noticias (filtros: party, sentiment) |
| `/noticias/{id}` | GET | Detalle de una noticia |
| `/events` | GET | Lista eventos políticos (filtros: category, party, severity) |
| `/events/{id}` | GET | Detalle de un evento con posturas de partidos |
| `/investiga` | GET | Partidos con conteo de eventos cuestionables |
| `/investiga/{jne_id}` | GET | Eventos cuestionables de un partido específico |
| `/docs` | GET | Documentación OpenAPI (Swagger) |

## Stack técnico

- **Backend**: FastAPI, psycopg (raw SQL), pgvector, sentence-transformers
- **LLM**: Claude Haiku (generación), Claude Sonnet (extracción de posiciones)
- **Embeddings**: BAAI/bge-m3 (768 dim, local, gratuito)
- **Base de datos**: PostgreSQL 16 + pgvector (HNSW index, cosine)
- **Frontend**: Astro (SSG) + Preact islands + Tailwind CSS v4
- **Infraestructura**: Docker Compose, uv, npm

## Todos los comandos

```bash
# Desarrollo
make setup                # Setup completo desde cero
make dev                  # Servidor API (hot-reload)
make dev-frontend         # Servidor frontend (dev)
make build                # Construir frontend estático

# Base de datos
make db-up / db-down      # Iniciar / detener PostgreSQL
make migrate              # Ejecutar migraciones pendientes

# Pipeline de datos (SCOPE=presidential|formula|all)
make pipeline             # Pipeline completo (fetch + collect + extract)
make fetch-candidates     # Paso 1: obtener candidatos del JNE
make collect-content      # Paso 2: planes + noticias + eventos
make extract-positions    # Paso 3: extraer posiciones con LLM

# Utilidades
make clean                # Limpiar artefactos de build
make help                 # Muestra todos los comandos
```

## Licencia

MIT
