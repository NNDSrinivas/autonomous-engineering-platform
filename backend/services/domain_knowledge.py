"""
Domain-Specific Knowledge for NAVI

Provides specialized context and best practices for:
1. Backend Development (Python, Node.js, Go)
2. Frontend Development (React, Vue, Angular)
3. DevOps (Docker, Kubernetes, CI/CD)
4. Data Engineering (SQL, Pandas, ETL)

This knowledge is injected into NAVI's prompts to improve
accuracy and adherence to best practices.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum


class DomainType(Enum):
    """
    All supported domains for NAVI's universal capabilities.
    NAVI works with ANY language, framework, or technology.
    """

    # Backend Languages
    BACKEND_PYTHON = "backend_python"
    BACKEND_NODE = "backend_node"
    BACKEND_GO = "backend_go"
    BACKEND_JAVA = "backend_java"
    BACKEND_CSHARP = "backend_csharp"
    BACKEND_RUST = "backend_rust"
    BACKEND_RUBY = "backend_ruby"
    BACKEND_PHP = "backend_php"
    BACKEND_SCALA = "backend_scala"
    BACKEND_ELIXIR = "backend_elixir"
    BACKEND_KOTLIN = "backend_kotlin"

    # Frontend
    FRONTEND_REACT = "frontend_react"
    FRONTEND_VUE = "frontend_vue"
    FRONTEND_ANGULAR = "frontend_angular"
    FRONTEND_SVELTE = "frontend_svelte"
    FRONTEND_NEXTJS = "frontend_nextjs"
    FRONTEND_HTML_CSS = "frontend_html_css"
    FRONTEND_HTMX = "frontend_htmx"
    FRONTEND_ASTRO = "frontend_astro"

    # Mobile
    MOBILE_REACT_NATIVE = "mobile_react_native"
    MOBILE_FLUTTER = "mobile_flutter"
    MOBILE_IOS_SWIFT = "mobile_ios_swift"
    MOBILE_ANDROID_KOTLIN = "mobile_android_kotlin"

    # DevOps & Infrastructure
    DEVOPS_DOCKER = "devops_docker"
    DEVOPS_KUBERNETES = "devops_kubernetes"
    DEVOPS_CICD = "devops_cicd"
    DEVOPS_TERRAFORM = "devops_terraform"
    DEVOPS_AWS = "devops_aws"
    DEVOPS_GCP = "devops_gcp"
    DEVOPS_AZURE = "devops_azure"
    DEVOPS_ANSIBLE = "devops_ansible"
    DEVOPS_PULUMI = "devops_pulumi"

    # Data & Analytics
    DATA_SQL = "data_sql"
    DATA_PANDAS = "data_pandas"
    DATA_SPARK = "data_spark"
    DATA_ML = "data_ml"
    DATA_AIRFLOW = "data_airflow"
    DATA_KAFKA = "data_kafka"
    DATA_SNOWFLAKE = "data_snowflake"
    DATA_DBT = "data_dbt"

    # Systems Programming
    SYSTEMS_C = "systems_c"
    SYSTEMS_CPP = "systems_cpp"
    SYSTEMS_EMBEDDED = "systems_embedded"
    SYSTEMS_WEBASSEMBLY = "systems_webassembly"

    # Scripting
    SCRIPTING_BASH = "scripting_bash"
    SCRIPTING_POWERSHELL = "scripting_powershell"

    # Blockchain & Web3
    BLOCKCHAIN_SOLIDITY = "blockchain_solidity"
    BLOCKCHAIN_SOLANA = "blockchain_solana"
    BLOCKCHAIN_WEB3 = "blockchain_web3"

    # Functional Programming
    FUNCTIONAL_HASKELL = "functional_haskell"
    FUNCTIONAL_CLOJURE = "functional_clojure"
    FUNCTIONAL_FP = "functional_fp"

    # Game Development
    GAMEDEV_UNITY = "gamedev_unity"
    GAMEDEV_UNREAL = "gamedev_unreal"
    GAMEDEV_GODOT = "gamedev_godot"

    # Security
    SECURITY_GENERAL = "security_general"

    # API Design
    API_REST = "api_rest"
    API_GRAPHQL = "api_graphql"
    API_GRPC = "api_grpc"

    # Observability
    OBSERVABILITY = "observability"

    # Universal / General
    GENERAL = "general"


@dataclass
class DomainKnowledge:
    domain: DomainType
    best_practices: List[str]
    common_patterns: Dict[str, str]
    antipatterns: List[str]
    file_conventions: Dict[str, str]  # filename -> description
    import_conventions: List[str]
    testing_conventions: List[str]


# ============================================================
# BACKEND - PYTHON
# ============================================================

BACKEND_PYTHON = DomainKnowledge(
    domain=DomainType.BACKEND_PYTHON,
    best_practices=[
        "Use type hints for function parameters and return values",
        "Use Pydantic for data validation and serialization",
        "Use async/await for I/O-bound operations",
        "Use dependency injection for better testability",
        "Follow PEP 8 style guidelines",
        "Use environment variables for configuration (never hardcode secrets)",
        "Use connection pooling for database connections",
        "Implement proper error handling with custom exceptions",
        "Use logging instead of print statements",
        "Write docstrings for public functions and classes",
    ],
    common_patterns={
        "fastapi_router": """from fastapi import APIRouter, Depends, HTTPException
from typing import List
from .models import ItemCreate, ItemResponse
from .service import ItemService

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/", response_model=List[ItemResponse])
async def list_items(service: ItemService = Depends()):
    return await service.get_all()

@router.post("/", response_model=ItemResponse, status_code=201)
async def create_item(item: ItemCreate, service: ItemService = Depends()):
    return await service.create(item)""",
        "pydantic_model": """from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    price: float = Field(..., gt=0)

class ItemCreate(ItemBase):
    pass

class ItemResponse(ItemBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True""",
        "sqlalchemy_model": """from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    price = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="items")""",
        "repository_pattern": """from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic
from sqlalchemy.orm import Session

T = TypeVar("T")

class Repository(ABC, Generic[T]):
    @abstractmethod
    async def get(self, id: int) -> Optional[T]:
        pass

    @abstractmethod
    async def get_all(self) -> List[T]:
        pass

    @abstractmethod
    async def create(self, entity: T) -> T:
        pass

    @abstractmethod
    async def update(self, id: int, entity: T) -> Optional[T]:
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        pass""",
    },
    antipatterns=[
        "Don't use mutable default arguments",
        "Don't catch bare exceptions (except Exception)",
        "Don't use global variables for state",
        "Don't hardcode configuration values",
        "Don't ignore return values from async operations",
        "Don't use string formatting for SQL queries (use parameterized queries)",
    ],
    file_conventions={
        "models.py": "Pydantic models for request/response schemas",
        "schemas.py": "Alternative name for Pydantic models",
        "database.py": "Database connection and session management",
        "crud.py": "Database CRUD operations",
        "routes.py": "API route definitions (FastAPI routers)",
        "services.py": "Business logic layer",
        "dependencies.py": "FastAPI dependencies",
        "config.py": "Configuration and settings",
        "utils.py": "Utility functions",
        "exceptions.py": "Custom exception classes",
    },
    import_conventions=[
        "Group imports: stdlib, third-party, local",
        "Use absolute imports for clarity",
        "Import specific functions/classes, not entire modules",
    ],
    testing_conventions=[
        "Use pytest as the test framework",
        "Name test files as test_*.py",
        "Use fixtures for common setup",
        "Use pytest.mark.asyncio for async tests",
        "Mock external dependencies",
    ],
)


# ============================================================
# BACKEND - NODE.JS
# ============================================================

BACKEND_NODE = DomainKnowledge(
    domain=DomainType.BACKEND_NODE,
    best_practices=[
        "Use TypeScript for type safety",
        "Use async/await instead of callbacks",
        "Use environment variables for configuration",
        "Implement proper error handling middleware",
        "Use connection pooling for databases",
        "Validate input data with libraries like Joi or Zod",
        "Use helmet for security headers",
        "Use compression middleware",
        "Implement rate limiting",
        "Use structured logging (winston, pino)",
    ],
    common_patterns={
        "express_app": """import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { errorHandler } from './middleware/errorHandler';
import { userRouter } from './routes/users';

const app = express();

app.use(helmet());
app.use(cors());
app.use(express.json());

app.use('/api/users', userRouter);
app.use(errorHandler);

export default app;""",
        "express_router": """import { Router } from 'express';
import { UserController } from '../controllers/userController';
import { validateRequest } from '../middleware/validateRequest';
import { createUserSchema } from '../schemas/userSchema';

const router = Router();
const controller = new UserController();

router.get('/', controller.getAll);
router.get('/:id', controller.getById);
router.post('/', validateRequest(createUserSchema), controller.create);
router.put('/:id', validateRequest(createUserSchema), controller.update);
router.delete('/:id', controller.delete);

export { router as userRouter };""",
        "typescript_interface": """export interface User {
  id: string;
  email: string;
  name: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface CreateUserDTO {
  email: string;
  name: string;
  password: string;
}

export interface UpdateUserDTO {
  name?: string;
  email?: string;
}""",
    },
    antipatterns=[
        "Don't use var, use const/let",
        "Don't use synchronous file operations in request handlers",
        "Don't store secrets in code",
        "Don't trust user input without validation",
        "Don't catch errors without proper handling",
    ],
    file_conventions={
        "app.ts": "Express application setup",
        "server.ts": "Server entry point",
        "routes/": "Route definitions directory",
        "controllers/": "Request handlers",
        "services/": "Business logic",
        "models/": "Database models",
        "middleware/": "Express middleware",
        "utils/": "Utility functions",
        "types/": "TypeScript type definitions",
    },
    import_conventions=[
        "Use ES6 imports (import/export)",
        "Use path aliases for cleaner imports",
        "Group imports by source",
    ],
    testing_conventions=[
        "Use Jest or Vitest for testing",
        "Use supertest for API testing",
        "Mock database calls",
        "Use test containers for integration tests",
    ],
)


# ============================================================
# FRONTEND - REACT
# ============================================================

FRONTEND_REACT = DomainKnowledge(
    domain=DomainType.FRONTEND_REACT,
    best_practices=[
        "Use functional components with hooks",
        "Use TypeScript for type safety",
        "Keep components small and focused",
        "Use custom hooks for reusable logic",
        "Implement proper error boundaries",
        "Use React.memo for expensive components",
        "Use useMemo and useCallback appropriately",
        "Manage state close to where it's used",
        "Use context for truly global state",
        "Implement proper loading and error states",
    ],
    common_patterns={
        "functional_component": """import { useState, useEffect } from 'react';

interface Props {
  initialValue?: string;
  onChange?: (value: string) => void;
}

export const MyComponent: React.FC<Props> = ({ initialValue = '', onChange }) => {
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    onChange?.(value);
  }, [value, onChange]);

  return (
    <div className="my-component">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
    </div>
  );
};""",
        "custom_hook": """import { useState, useCallback } from 'react';

interface UseToggleReturn {
  value: boolean;
  toggle: () => void;
  setTrue: () => void;
  setFalse: () => void;
}

export const useToggle = (initialValue = false): UseToggleReturn => {
  const [value, setValue] = useState(initialValue);

  const toggle = useCallback(() => setValue((v) => !v), []);
  const setTrue = useCallback(() => setValue(true), []);
  const setFalse = useCallback(() => setValue(false), []);

  return { value, toggle, setTrue, setFalse };
};""",
        "context_provider": """import { createContext, useContext, useState, ReactNode } from 'react';

interface AuthContextType {
  user: User | null;
  login: (credentials: Credentials) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const login = async (credentials: Credentials) => {
    // Implementation
  };

  const logout = () => {
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};""",
    },
    antipatterns=[
        "Don't use index as key in lists with dynamic items",
        "Don't mutate state directly",
        "Don't overuse useEffect",
        "Don't create components inside components",
        "Don't ignore dependency arrays in hooks",
    ],
    file_conventions={
        "ComponentName.tsx": "Component file (PascalCase)",
        "useHookName.ts": "Custom hook file (camelCase with 'use' prefix)",
        "ComponentName.test.tsx": "Test file",
        "ComponentName.module.css": "CSS module",
        "types.ts": "TypeScript type definitions",
        "constants.ts": "Constants and configuration",
    },
    import_conventions=[
        "Import React hooks explicitly",
        "Group component imports together",
        "Import styles at the end",
    ],
    testing_conventions=[
        "Use React Testing Library",
        "Test user interactions, not implementation",
        "Use screen queries",
        "Mock API calls and context providers",
    ],
)


# ============================================================
# DEVOPS - DOCKER
# ============================================================

DEVOPS_DOCKER = DomainKnowledge(
    domain=DomainType.DEVOPS_DOCKER,
    best_practices=[
        "Use multi-stage builds to reduce image size",
        "Pin base image versions (avoid :latest)",
        "Run as non-root user",
        "Use .dockerignore to exclude unnecessary files",
        "Combine RUN commands to reduce layers",
        "Order instructions from least to most frequently changing",
        "Use COPY instead of ADD for simple file copying",
        "Clean up package manager caches in the same RUN command",
        "Use health checks",
        "Don't store secrets in images",
    ],
    common_patterns={
        "node_multistage": """# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM node:20-alpine AS production
WORKDIR /app
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
USER nodejs
EXPOSE 3000
CMD ["node", "dist/main.js"]""",
        "python_dockerfile": """FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]""",
        "docker_compose": """version: '3.8'

services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=mydb

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:""",
    },
    antipatterns=[
        "Don't use :latest tags in production",
        "Don't run as root",
        "Don't store secrets in environment variables in Dockerfile",
        "Don't install development dependencies in production images",
        "Don't forget to clean up package caches",
    ],
    file_conventions={
        "Dockerfile": "Main Dockerfile",
        "Dockerfile.dev": "Development Dockerfile",
        "docker-compose.yml": "Main compose file",
        "docker-compose.override.yml": "Development overrides",
        ".dockerignore": "Files to exclude from build context",
    },
    import_conventions=[],
    testing_conventions=[
        "Use docker-compose for local testing",
        "Test image builds in CI",
        "Scan images for vulnerabilities",
    ],
)


# ============================================================
# DEVOPS - CI/CD
# ============================================================

DEVOPS_CICD = DomainKnowledge(
    domain=DomainType.DEVOPS_CICD,
    best_practices=[
        "Use caching for dependencies",
        "Run tests in parallel when possible",
        "Use matrix builds for multiple versions/platforms",
        "Fail fast on errors",
        "Use secrets management, never hardcode",
        "Implement proper staging/production separation",
        "Use artifacts for build outputs",
        "Implement proper rollback strategies",
        "Use branch protection rules",
        "Implement security scanning in pipeline",
    ],
    common_patterns={
        "github_actions_ci": """name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18.x, 20.x]

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js ${{ matrix.node-version }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Lint
        run: npm run lint

      - name: Test
        run: npm test -- --coverage

      - name: Build
        run: npm run build""",
        "github_actions_deploy": """name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Login to ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push Docker image
        env:
          REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          REPOSITORY: my-app
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $REGISTRY/$REPOSITORY:$IMAGE_TAG .
          docker push $REGISTRY/$REPOSITORY:$IMAGE_TAG

      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster my-cluster --service my-service --force-new-deployment""",
    },
    antipatterns=[
        "Don't store secrets in workflow files",
        "Don't skip tests in CI",
        "Don't deploy without testing",
        "Don't use hardcoded versions",
    ],
    file_conventions={
        ".github/workflows/ci.yml": "CI workflow",
        ".github/workflows/deploy.yml": "Deployment workflow",
        ".github/workflows/release.yml": "Release workflow",
    },
    import_conventions=[],
    testing_conventions=[
        "Run linting before tests",
        "Run tests with coverage",
        "Run security scans",
    ],
)


# ============================================================
# DATA ENGINEERING
# ============================================================

DATA_PANDAS = DomainKnowledge(
    domain=DomainType.DATA_PANDAS,
    best_practices=[
        "Use vectorized operations instead of loops",
        "Use appropriate data types (category for strings with few unique values)",
        "Use chunked reading for large files",
        "Use query() for complex filtering",
        "Use pipe() for chaining operations",
        "Handle missing data explicitly",
        "Use copy() when modifying subsets",
        "Profile data before processing",
    ],
    common_patterns={
        "data_pipeline": """import pandas as pd
from typing import Optional

class DataPipeline:
    def __init__(self, source_path: str):
        self.source_path = source_path
        self.df: Optional[pd.DataFrame] = None

    def extract(self) -> 'DataPipeline':
        self.df = pd.read_csv(self.source_path)
        return self

    def transform(self) -> 'DataPipeline':
        if self.df is None:
            raise ValueError("Must extract before transform")

        self.df = (
            self.df
            .pipe(self._clean_column_names)
            .pipe(self._handle_missing)
            .pipe(self._convert_types)
        )
        return self

    def load(self, dest_path: str) -> None:
        if self.df is None:
            raise ValueError("Must transform before load")
        self.df.to_parquet(dest_path, index=False)

    def _clean_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        df.columns = df.columns.str.lower().str.replace(' ', '_')
        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.dropna(subset=['id'])

    def _convert_types(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.astype({'category_col': 'category'})""",
    },
    antipatterns=[
        "Don't iterate over DataFrame rows (use vectorized operations)",
        "Don't use chained indexing (use .loc or .iloc)",
        "Don't ignore data types",
        "Don't forget to handle missing data",
    ],
    file_conventions={
        "pipeline.py": "ETL pipeline classes",
        "transformers.py": "Data transformation functions",
        "validators.py": "Data validation functions",
        "utils.py": "Utility functions",
    },
    import_conventions=[
        "import pandas as pd",
        "import numpy as np",
    ],
    testing_conventions=[
        "Test with sample data",
        "Validate schema after transformations",
        "Test edge cases (empty, null, duplicates)",
    ],
)


# ============================================================
# DOMAIN DETECTION AND CONTEXT GENERATION
# ============================================================

DOMAIN_KNOWLEDGE_MAP = {
    DomainType.BACKEND_PYTHON: BACKEND_PYTHON,
    DomainType.BACKEND_NODE: BACKEND_NODE,
    DomainType.FRONTEND_REACT: FRONTEND_REACT,
    DomainType.DEVOPS_DOCKER: DEVOPS_DOCKER,
    DomainType.DEVOPS_CICD: DEVOPS_CICD,
    DomainType.DATA_PANDAS: DATA_PANDAS,
}


def detect_domain(
    message: str, project_type: str = None, technologies: List[str] = None
) -> DomainType:
    """
    Detect the domain based on message content and project context.
    Supports ALL major languages, frameworks, and technology stacks.
    """
    message_lower = message.lower()
    technologies = technologies or []
    tech_lower = [t.lower() for t in technologies]

    # Backend Python
    if any(
        kw in message_lower
        for kw in ["fastapi", "django", "flask", "pydantic", "sqlalchemy", "celery"]
    ):
        return DomainType.BACKEND_PYTHON
    if project_type == "python" or "python" in tech_lower:
        return DomainType.BACKEND_PYTHON

    # Backend Node
    if any(
        kw in message_lower
        for kw in ["express", "nestjs", "koa", "hapi", "npm", "yarn", "bun"]
    ):
        return DomainType.BACKEND_NODE
    if project_type in ["nodejs", "node"] or "node" in tech_lower:
        return DomainType.BACKEND_NODE

    # Backend Go
    if any(
        kw in message_lower
        for kw in ["golang", " go ", "gin", "echo", "fiber", "goroutine"]
    ):
        return DomainType.BACKEND_GO
    if project_type == "go" or "go" in tech_lower:
        return DomainType.BACKEND_GO

    # Backend Java
    if any(
        kw in message_lower
        for kw in [
            "spring",
            "springboot",
            "java",
            "maven",
            "gradle",
            "jpa",
            "hibernate",
        ]
    ):
        return DomainType.BACKEND_JAVA
    if project_type == "java" or "java" in tech_lower:
        return DomainType.BACKEND_JAVA

    # Backend C#
    if any(
        kw in message_lower
        for kw in [
            "c#",
            "csharp",
            ".net",
            "dotnet",
            "aspnet",
            "asp.net",
            "entity framework",
        ]
    ):
        return DomainType.BACKEND_CSHARP
    if project_type in ["csharp", "dotnet"] or any(
        t in tech_lower for t in ["csharp", ".net"]
    ):
        return DomainType.BACKEND_CSHARP

    # Backend Rust
    if any(kw in message_lower for kw in ["rust", "cargo", "tokio", "actix", "rocket"]):
        return DomainType.BACKEND_RUST
    if project_type == "rust" or "rust" in tech_lower:
        return DomainType.BACKEND_RUST

    # Backend Ruby
    if any(kw in message_lower for kw in ["ruby", "rails", "sinatra", "rake", "gem"]):
        return DomainType.BACKEND_RUBY
    if project_type == "ruby" or "ruby" in tech_lower:
        return DomainType.BACKEND_RUBY

    # Backend PHP
    if any(
        kw in message_lower
        for kw in ["php", "laravel", "symfony", "composer", "wordpress"]
    ):
        return DomainType.BACKEND_PHP
    if project_type == "php" or "php" in tech_lower:
        return DomainType.BACKEND_PHP

    # Frontend React
    if any(
        kw in message_lower
        for kw in ["react", "jsx", "tsx", "hooks", "useState", "useEffect", "redux"]
    ):
        return DomainType.FRONTEND_REACT
    if "react" in tech_lower:
        return DomainType.FRONTEND_REACT

    # Frontend Next.js
    if any(
        kw in message_lower
        for kw in ["next.js", "nextjs", "next", "getserverside", "getstatic"]
    ):
        return DomainType.FRONTEND_NEXTJS

    # Frontend Vue
    if any(
        kw in message_lower
        for kw in ["vue", "vuex", "pinia", "composition api", "nuxt"]
    ):
        return DomainType.FRONTEND_VUE

    # Frontend Angular
    if any(
        kw in message_lower for kw in ["angular", "rxjs", "ngrx", "ng ", "ngmodule"]
    ):
        return DomainType.FRONTEND_ANGULAR

    # Frontend Svelte
    if any(kw in message_lower for kw in ["svelte", "sveltekit"]):
        return DomainType.FRONTEND_SVELTE

    # Mobile React Native
    if any(kw in message_lower for kw in ["react native", "react-native", "expo"]):
        return DomainType.MOBILE_REACT_NATIVE

    # Mobile Flutter
    if any(kw in message_lower for kw in ["flutter", "dart", "widget"]):
        return DomainType.MOBILE_FLUTTER

    # Mobile iOS
    if any(
        kw in message_lower
        for kw in ["swift", "ios", "xcode", "uikit", "swiftui", "cocoapods"]
    ):
        return DomainType.MOBILE_IOS_SWIFT

    # Mobile Android
    if any(
        kw in message_lower for kw in ["kotlin", "android", "jetpack", "gradle android"]
    ):
        return DomainType.MOBILE_ANDROID_KOTLIN

    # DevOps Docker
    if any(
        kw in message_lower for kw in ["docker", "dockerfile", "container", "compose"]
    ):
        return DomainType.DEVOPS_DOCKER

    # DevOps Kubernetes
    if any(
        kw in message_lower
        for kw in ["kubernetes", "k8s", "kubectl", "helm", "pod", "deployment"]
    ):
        return DomainType.DEVOPS_KUBERNETES

    # DevOps Terraform
    if any(
        kw in message_lower
        for kw in ["terraform", "hcl", "tf ", "infrastructure as code"]
    ):
        return DomainType.DEVOPS_TERRAFORM

    # DevOps AWS
    if any(
        kw in message_lower
        for kw in ["aws", "lambda", "s3", "ec2", "cloudformation", "cdk"]
    ):
        return DomainType.DEVOPS_AWS

    # DevOps GCP
    if any(
        kw in message_lower
        for kw in ["gcp", "google cloud", "gke", "cloud run", "bigquery"]
    ):
        return DomainType.DEVOPS_GCP

    # DevOps Azure
    if any(kw in message_lower for kw in ["azure", "aks", "azure function"]):
        return DomainType.DEVOPS_AZURE

    # DevOps CI/CD
    if any(
        kw in message_lower
        for kw in ["github actions", "ci/cd", "jenkins", "gitlab ci", "circleci"]
    ):
        return DomainType.DEVOPS_CICD

    # Data Pandas
    if any(
        kw in message_lower for kw in ["pandas", "dataframe", "etl", "data pipeline"]
    ):
        return DomainType.DATA_PANDAS

    # Data SQL
    if any(
        kw in message_lower
        for kw in ["sql", "query", "database", "postgresql", "mysql", "sqlite"]
    ):
        return DomainType.DATA_SQL

    # Data Spark
    if any(kw in message_lower for kw in ["spark", "pyspark", "databricks"]):
        return DomainType.DATA_SPARK

    # Data ML
    if any(
        kw in message_lower
        for kw in ["machine learning", "ml", "tensorflow", "pytorch", "scikit", "model"]
    ):
        return DomainType.DATA_ML

    # Data Airflow
    if any(kw in message_lower for kw in ["airflow", "dag", "data orchestration"]):
        return DomainType.DATA_AIRFLOW

    # Systems C
    if any(
        kw in message_lower for kw in [" c ", "gcc", "makefile", "pointer", "malloc"]
    ):
        return DomainType.SYSTEMS_C

    # Systems C++
    if any(kw in message_lower for kw in ["c++", "cpp", "cmake", "stl", "template"]):
        return DomainType.SYSTEMS_CPP

    # Scripting Bash
    if any(
        kw in message_lower
        for kw in ["bash", "shell", "sh ", "#!/bin", "linux command"]
    ):
        return DomainType.SCRIPTING_BASH

    # Scripting PowerShell
    if any(kw in message_lower for kw in ["powershell", "ps1", "windows script"]):
        return DomainType.SCRIPTING_POWERSHELL

    # ==================== NEW DOMAINS ====================

    # Backend Scala
    if any(
        kw in message_lower
        for kw in ["scala", "sbt", "akka", "play framework", "zio", "cats"]
    ):
        return DomainType.BACKEND_SCALA
    if project_type == "scala" or "scala" in tech_lower:
        return DomainType.BACKEND_SCALA

    # Backend Elixir
    if any(
        kw in message_lower
        for kw in ["elixir", "phoenix", "erlang", "otp", "genserver", "ecto"]
    ):
        return DomainType.BACKEND_ELIXIR
    if project_type == "elixir" or "elixir" in tech_lower:
        return DomainType.BACKEND_ELIXIR

    # Backend Kotlin (server-side)
    if any(
        kw in message_lower
        for kw in ["ktor", "kotlin server", "kotlin backend", "spring kotlin"]
    ):
        return DomainType.BACKEND_KOTLIN

    # Blockchain Solidity / Ethereum
    if any(
        kw in message_lower
        for kw in [
            "solidity",
            "smart contract",
            "ethereum",
            "hardhat",
            "truffle",
            "foundry",
            "erc20",
            "erc721",
        ]
    ):
        return DomainType.BLOCKCHAIN_SOLIDITY

    # Blockchain Solana
    if any(
        kw in message_lower for kw in ["solana", "anchor", "rust solana", "spl token"]
    ):
        return DomainType.BLOCKCHAIN_SOLANA

    # Blockchain Web3 General
    if any(
        kw in message_lower
        for kw in [
            "web3",
            "blockchain",
            "defi",
            "nft",
            "dapp",
            "metamask",
            "wagmi",
            "ethers.js",
            "viem",
        ]
    ):
        return DomainType.BLOCKCHAIN_WEB3

    # Data Kafka
    if any(
        kw in message_lower
        for kw in ["kafka", "kafka streams", "confluent", "ksql", "schema registry"]
    ):
        return DomainType.DATA_KAFKA

    # Data Snowflake
    if any(kw in message_lower for kw in ["snowflake", "snowsql", "snowpark"]):
        return DomainType.DATA_SNOWFLAKE

    # Data dbt
    if any(
        kw in message_lower
        for kw in ["dbt", "dbt model", "dbt test", "data build tool"]
    ):
        return DomainType.DATA_DBT

    # DevOps Ansible
    if any(
        kw in message_lower
        for kw in ["ansible", "playbook", "ansible role", "ansible vault"]
    ):
        return DomainType.DEVOPS_ANSIBLE

    # DevOps Pulumi
    if any(kw in message_lower for kw in ["pulumi", "pulumi stack"]):
        return DomainType.DEVOPS_PULUMI

    # Systems Embedded
    if any(
        kw in message_lower
        for kw in [
            "embedded",
            "arduino",
            "esp32",
            "raspberry pi",
            "microcontroller",
            "rtos",
            "freertos",
            "firmware",
        ]
    ):
        return DomainType.SYSTEMS_EMBEDDED

    # Systems WebAssembly
    if any(kw in message_lower for kw in ["webassembly", "wasm", "emscripten", "wasi"]):
        return DomainType.SYSTEMS_WEBASSEMBLY

    # Functional Haskell
    if any(
        kw in message_lower
        for kw in ["haskell", "cabal", "stack haskell", "ghc", "monad"]
    ):
        return DomainType.FUNCTIONAL_HASKELL

    # Functional Clojure
    if any(
        kw in message_lower
        for kw in ["clojure", "clojurescript", "leiningen", "deps.edn"]
    ):
        return DomainType.FUNCTIONAL_CLOJURE

    # Functional Programming General
    if any(
        kw in message_lower
        for kw in [
            "functional programming",
            "pure function",
            "immutable",
            "functor",
            "algebraic data type",
        ]
    ):
        return DomainType.FUNCTIONAL_FP

    # Game Development Unity
    if any(
        kw in message_lower for kw in ["unity", "c# unity", "unity3d", "unity game"]
    ):
        return DomainType.GAMEDEV_UNITY

    # Game Development Unreal
    if any(
        kw in message_lower
        for kw in ["unreal", "unreal engine", "blueprint", "ue4", "ue5"]
    ):
        return DomainType.GAMEDEV_UNREAL

    # Game Development Godot
    if any(kw in message_lower for kw in ["godot", "gdscript", "godot engine"]):
        return DomainType.GAMEDEV_GODOT

    # API GraphQL
    if any(
        kw in message_lower
        for kw in ["graphql", "apollo", "schema graphql", "resolver", "gql"]
    ):
        return DomainType.API_GRAPHQL

    # API gRPC
    if any(
        kw in message_lower for kw in ["grpc", "protobuf", "protocol buffer", ".proto"]
    ):
        return DomainType.API_GRPC

    # API REST
    if any(kw in message_lower for kw in ["rest api", "restful", "openapi", "swagger"]):
        return DomainType.API_REST

    # Observability
    if any(
        kw in message_lower
        for kw in [
            "prometheus",
            "grafana",
            "datadog",
            "newrelic",
            "jaeger",
            "opentelemetry",
            "logging",
            "monitoring",
            "alerting",
        ]
    ):
        return DomainType.OBSERVABILITY

    # Security
    if any(
        kw in message_lower
        for kw in [
            "security",
            "auth",
            "oauth",
            "jwt",
            "encryption",
            "vulnerability",
            "penetration",
            "owasp",
        ]
    ):
        return DomainType.SECURITY_GENERAL

    # Frontend HTMX
    if any(kw in message_lower for kw in ["htmx", "hyperscript"]):
        return DomainType.FRONTEND_HTMX

    # Frontend Astro
    if any(kw in message_lower for kw in ["astro", "astro.build"]):
        return DomainType.FRONTEND_ASTRO

    return DomainType.GENERAL


def get_domain_context(domain: DomainType) -> str:
    """Generate context string for a domain to inject into prompts."""
    knowledge = DOMAIN_KNOWLEDGE_MAP.get(domain)
    if not knowledge:
        return ""

    lines = [f"\n=== DOMAIN EXPERTISE: {domain.value.upper()} ===\n"]

    # Best practices
    lines.append("**Best Practices:**")
    for practice in knowledge.best_practices[:5]:
        lines.append(f"- {practice}")

    # Anti-patterns
    lines.append("\n**Avoid:**")
    for antipattern in knowledge.antipatterns[:3]:
        lines.append(f"- {antipattern}")

    # File conventions
    if knowledge.file_conventions:
        lines.append("\n**File Conventions:**")
        for filename, desc in list(knowledge.file_conventions.items())[:5]:
            lines.append(f"- {filename}: {desc}")

    return "\n".join(lines)


def get_pattern_example(domain: DomainType, pattern_name: str) -> Optional[str]:
    """Get a code pattern example for a domain."""
    knowledge = DOMAIN_KNOWLEDGE_MAP.get(domain)
    if not knowledge:
        return None
    return knowledge.common_patterns.get(pattern_name)
