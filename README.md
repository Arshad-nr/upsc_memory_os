# UPSC Memory OS 🚀

A highly-scalable, AI-powered revision operating system perfectly tailored for UPSC aspirants. Uses localized Vector Retrieval-Augmented Generation (RAG), Supabase, and Gemini to generate dynamic quizzes, revision queues, and interactive flashcards.

## 🏗️ Architecture

```mermaid
graph LR
    subgraph Client
        Browser[User Browser]
    end
    subgraph Frontend["Frontend (Next.js 14)"]
        UI[App UI]
    end
    subgraph Backend["Backend (FastAPI)"]
        API[FastAPI Server]
        Auth[JWT Auth]
        RAG[RAG Engine]
    end
    subgraph ExternalResources [External Resources]
        DB[(Supabase PostgreSQL)]
        Qdrant[(Qdrant Cloud)]
        LLM[Google Gemini API]
    end
    
    Browser -- "HTTP/REST" --> UI
    UI -- "API Calls (CORS)" --> API
    API --> Auth
    API --> RAG
    RAG --> Qdrant
    RAG --> LLM
    API -.-> DB
```

### Tech Stack
- **Frontend**: Next.js 14, Tailwind CSS, TypeScript
- **Backend**: FastAPI, Python 3.11, LangChain
- **Database**: Supabase PostgreSQL (User auth, metadata, revision state)
- **Vector DB**: Qdrant Cloud (Embeddings & Semantic Search)
- **LLM**: Google Gemini (Question generation & intelligent synthesis)
- **CI/CD**: GitHub Actions (Docker, ECR, ECS)
- **Infrastructure**: AWS (ALB, ECS Fargate, VCP, provisioned via Terraform)
- **Evaluation**: RAGAS pipeline for autonomous RAG performance testing

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- Docker and Docker Compose
- API Keys: Google Gemini API, Qdrant Cloud Cluster, Supabase

### 2. Environment Setup
Add your secrets to the backend `.env` file (`upsc-memory-os/backend/.env`):
```env
DATABASE_URL=postgresql+asyncpg://user:pass@db.supabase.co:5432/postgres
JWT_SECRET=your_secret_here
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
EMBEDDING_MODEL=all-MiniLM-L6-v2
QDRANT_URL=https://your-cluster.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_api_key_here
ENVIRONMENT=development
```

### 3. Run via Docker Compose
This spins up both the FastAPI backend and Next.js frontend in isolated containers:
```bash
docker-compose up --build -d
```
- **Frontend URL**: [http://localhost:3000](http://localhost:3000)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🚀 AWS Cloud Deployment (Terraform)

This project has complete Infrastructure as Code (IaC) written in Terraform for high-availability AWS deployments.

### Initial Setup
```bash
cd terraform
# Copy example variables and fill in your real API keys
cp terraform.tfvars.example terraform.tfvars

terraform init
terraform apply
```

### CI/CD Deployment Flow
Once Terraform has provisioned the infrastructure:
1. Merge your code to the `main` branch.
2. GitHub Actions (`ci.yml`) will automatically:
   - Lint & verify Python/TS syntax.
   - Build multi-stage optimized Docker images.
   - Push to Amazon Elastic Container Registry (ECR).
   - Trigger a rolling 0-downtime update on ECS Fargate.

---

## 🧪 Evaluation & Testing

RAGAS evaluation is configured into the CI/CD pipeline (`ragas-eval.yml`). It tests the quality of the LLM responses by looking at context precision, answer relevance, and factual correctness.

- Runs on a **weekly schedule** (Sunday 6AM IST) to detect model degradation.
- Can be **manually triggered** via the GitHub Actions dashboard.
- Results are uploaded as downloadable `.csv` artifacts right in the Actions summary tab.
