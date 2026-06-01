# AI Research Assistant - Production-Grade RAG System

A production-ready Retrieval-Augmented Generation (RAG) system that allows users to upload PDFs, chat with documents, and receive accurate answers with citations. Built for portfolio and interview excellence.

## 🎯 Project Highlights

- **Full-Stack Architecture**: Next.js frontend + FastAPI backend + ChromaDB vector store
- **Production-Grade**: Error handling, logging, authentication, rate limiting, caching
- **Scalable Design**: Async operations, connection pooling, horizontal scaling ready
- **Advanced RAG**: Hybrid search, reranking, multi-document reasoning, streaming responses
- **Enterprise Features**: JWT authentication, PostgreSQL persistence, Redis caching, WebSocket support

## 🏗️ System Architecture

```
Frontend (Next.js)
      ↓
FastAPI Backend (Python)
      ↓
┌─────────────────────────────┐
│  Microservices              │
├─────────────────────────────┤
│ • PDF Processing            │
│ • Chunking & Embeddings     │
│ • Vector Retrieval          │
│ • LLM Integration           │
│ • Chat Management           │
│ • Authentication            │
└─────────────────────────────┘
      ↓
┌─────────────────────────────┐
│  Data Layer                 │
├─────────────────────────────┤
│ • PostgreSQL (metadata)     │
│ • ChromaDB (vectors)        │
│ • Redis (cache)             │
└─────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- OpenAI API key (or Ollama for local)

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env.local
# Edit .env.local with your settings

# Start database and cache (via Docker)
docker-compose up -d

# Initialize database
python -c "from app.dependencies import init_db; import asyncio; asyncio.run(init_db())"

# Run server
python -m uvicorn app.main:app --reload
```

Server runs on `http://localhost:8000`
- API Docs: http://localhost:8000/api/docs
- Health Check: http://localhost:8000/api/health

### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Setup environment
cp .env.example .env.local

# Start development server
npm run dev
```

Frontend runs on `http://localhost:3000`

## 📁 Project Structure

```
ai-research-assistant/
├── backend/                          # Python FastAPI backend
│   ├── app/
│   │   ├── api/routes/              # API endpoints
│   │   ├── services/                # Business logic
│   │   ├── models/                  # ORM & schemas
│   │   ├── utils/                   # Helpers & errors
│   │   ├── cache/                   # Redis client
│   │   ├── middleware/              # Auth & error handling
│   │   ├── config.py                # Configuration
│   │   ├── dependencies.py          # Database & DI
│   │   └── main.py                  # FastAPI app
│   ├── tests/                       # Unit & integration tests
│   ├── migrations/                  # Alembic migrations
│   ├── requirements.txt             # Python dependencies
│   ├── Dockerfile
│   └── docker-compose.yml
├── frontend/                        # Next.js React app
│   ├── src/
│   │   ├── app/                     # Pages
│   │   ├── components/              # React components
│   │   ├── hooks/                   # Custom hooks
│   │   ├── lib/                     # Utilities
│   │   └── styles/                  # TailwindCSS
│   ├── package.json
│   └── tsconfig.json
├── docs/                            # Documentation
│   ├── SYSTEM_ARCHITECTURE.md       # System design
│   ├── PHASE_1_IMPLEMENTATION.md    # Phase 1 guide
│   ├── API_DOCUMENTATION.md         # API spec
│   ├── DEPLOYMENT.md                # Docker & cloud
│   └── CV_SUMMARY.md                # Portfolio points
└── docker-compose.yml               # Multi-service orchestration
```


## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Next.js + TypeScript + TailwindCSS | Modern, performant, great DX |
| Backend | FastAPI (Python) | Fast, async, great for ML workloads |
| Embeddings | Sentence-Transformers (BGE) | Better than OpenAI for RAG |
| Vector DB | ChromaDB | Lightweight, persistent, no infrastructure |
| LLM | OpenAI API / Ollama | Best quality (GPT-4) with local fallback |
| Framework | LangChain | Mature, flexible, tool integration |
| Database | PostgreSQL | ACID, full-text search, JSON support |
| Cache | Redis | Sub-ms latency, session management |
| Testing | Pytest | Comprehensive testing framework |
| Deployment | Docker + Docker Compose | Container orchestration |

## 📊 Data Flow

### RAG Pipeline
```
User Query
    ↓
[Generate Embedding]
    ↓
[Retrieve Top-K Chunks]
    ↓
[Optional: Rerank]
    ↓
[Build Prompt with Context]
    ↓
[Call LLM]
    ↓
[Extract Citations]
    ↓
[Stream Response to User]
```

## 🔐 Security Features

- JWT authentication with refresh tokens
- Password hashing (bcrypt)
- Rate limiting (Redis-backed)
- Input validation (Pydantic)
- SQL injection prevention (ORM)
- CORS configuration
- HTTPS enforcement (production)
- Audit logging

## 📈 Scalability

- **Horizontal**: Stateless FastAPI, load balancer ready
- **Database**: Read replicas, connection pooling
- **Cache**: Redis Cluster support
- **Async**: Non-blocking I/O for high throughput
- **Batch Processing**: Embedding generation in batches

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# All tests with coverage
pytest --cov=app --cov-report=html

# Specific test
pytest tests/test_auth.py::test_user_registration -v
```

## 📚 Documentation

- **[System Architecture](docs/SYSTEM_ARCHITECTURE.md)** - High-level design, tech decisions
- **[Phase 1 Implementation](docs/PHASE_1_IMPLEMENTATION.md)** - Setup guide, testing, debugging
- **[API Documentation](docs/API_DOCUMENTATION.md)** - All endpoints with examples
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Docker, Kubernetes, cloud setup
- **[CV Summary](docs/CV_SUMMARY.md)** - Portfolio points for interviews

## 🚢 Deployment

### Local Development
```bash
docker-compose up -d  # Starts PostgreSQL, Redis, Backend
npm run dev           # Starts Frontend (separate)
```

### Production
See [Deployment Guide](docs/DEPLOYMENT.md) for:
- Docker image optimization
- Kubernetes deployment
- AWS/GCP/Azure setup
- CI/CD pipeline
- Monitoring & logging

## 📝 API Examples

### Health Check
```bash
curl http://localhost:8000/api/health
```

### Register User (Phase 7)
```bash
curl -X POST http://localhost:8000/api/auth/register \\
  -H \"Content-Type: application/json\" \\
  -d '{
    \"email\": \"user@example.com\",
    \"username\": \"user\",
    \"password\": \"SecurePass123!\"
  }'
```

### Upload PDF (Phase 2)
```bash
curl -X POST http://localhost:8000/api/documents/upload \\
  -H \"Authorization: Bearer <token>\" \\
  -F \"file=@research_paper.pdf\"
```

### Chat with Document (Phase 5)
```bash
curl -X POST http://localhost:8000/api/chat \\
  -H \"Authorization: Bearer <token>\" \\
  -H \"Content-Type: application/json\" \\
  -d '{
    \"content\": \"What is the main contribution?\",
    \"document_ids\": [\"doc-uuid\"]
  }'
```

## 💡 Key Design Decisions

1. **FastAPI over Flask**: Better async support, 30-40% faster, built-in validation
2. **PostgreSQL + ChromaDB**: Separation of concerns (metadata vs vectors)
3. **LangChain over LlamaIndex**: More mature, better tool integration
4. **BGE Embeddings over OpenAI**: 15% better for RAG, 10x cheaper
5. **Redis over In-Memory**: Persistent across deployments, cluster support
6. **Docker Compose**: Easy multi-service orchestration for development

## 🐛 Troubleshooting

### PostgreSQL Connection Error
```bash
docker ps  # Check if postgres container is running
docker logs postgres_ai  # View logs
```

### Redis Connection Error
```bash
docker ps  # Check if redis container is running
redis-cli ping  # Test connection
```

### Port Already in Use
```bash
# Find process on port 8000
lsof -i :8000
# Kill process
kill -9 <PID>
```

See [Phase 1 Implementation](docs/PHASE_1_IMPLEMENTATION.md) for detailed troubleshooting.

## 📈 Performance Metrics (Target)

- API response time: < 200ms (with cache)
- Embedding generation: < 500ms for document
- Search retrieval: < 100ms
- LLM response time: 2-5s (streaming)
- Concurrent users: 1000+ (with horizontal scaling)

## 🎓 Learning Outcomes

This project demonstrates:

1. **Full-Stack Development**: Frontend + backend + infrastructure
2. **RAG Architecture**: Embeddings, vector search, LLM integration
3. **Production Engineering**: Error handling, logging, monitoring
4. **Database Design**: Relational + vector databases
5. **API Design**: RESTful + WebSocket, authentication
6. **DevOps**: Docker, Docker Compose, deployment strategies
7. **Testing**: Unit, integration, performance testing
8. **Clean Code**: Modular architecture, separation of concerns

## 📖 Interview Topics

Perfect for discussing:
- System design at scale
- Vector database trade-offs
- Embedding model selection
- RAG pipeline architecture
- Production deployment considerations
- Trade-offs: cost vs. quality (OpenAI vs. Ollama)
- Scaling strategies for ML workloads

## 🤝 Contributing

This is a portfolio project. For improvements:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Commit changes (`git commit -am 'Add improvement'`)
4. Push to branch (`git push origin feature/improvement`)
5. Create Pull Request

## 📄 License

MIT License - Feel free to use this project for portfolio and learning.

## 🙋 Support

For issues or questions:
1. Check [Troubleshooting](docs/PHASE_1_IMPLEMENTATION.md#part-4-common-errors--fixes)
2. Review [API Documentation](docs/API_DOCUMENTATION.md)
3. See [System Architecture](docs/SYSTEM_ARCHITECTURE.md) for design questions

---

**Last Updated**: 2026-05-31  
**Version**: 1.0.0
