"""
Scaffolding tools for NAVI agent.

Provides tools to scaffold new projects and add features to existing projects.
Supports multiple frameworks and project types without hardcoding - dynamically
detects requirements and generates appropriate project structures.
"""

import os
import json
import re
from typing import Any, Dict, Optional
import structlog

from backend.services.connector_base import ToolResult
from backend.services.project_scaffolder import (
    ProjectScaffolder,
    ProjectType,
    ProjectScaffoldRequest,
)

logger = structlog.get_logger(__name__)


# Extended project types beyond the basic scaffolder
EXTENDED_PROJECT_TYPES = {
    "nextjs": ProjectType.NEXTJS,
    "react": ProjectType.REACT,
    "vite-react": ProjectType.VITE_REACT,
    "vite-vue": ProjectType.VITE_VUE,
    "vite": ProjectType.VITE_REACT,
    "express": ProjectType.EXPRESS,
    "python": ProjectType.PYTHON,
    "fastapi": ProjectType.PYTHON,
    "flask": ProjectType.PYTHON,
    "django": ProjectType.PYTHON,
    "static-html": ProjectType.STATIC_HTML,
    "html": ProjectType.STATIC_HTML,
    "go": ProjectType.UNKNOWN,  # Will use custom scaffolding
    "rust": ProjectType.UNKNOWN,  # Will use custom scaffolding
    "nestjs": ProjectType.EXPRESS,  # NestJS is Node-based
}

# Feature scaffolding templates
FEATURE_TEMPLATES = {
    "api-route": {
        "nextjs": {
            "path": "app/api/{name}/route.ts",
            "content": """import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    // TODO: Implement GET handler
    return NextResponse.json({ message: 'GET {name}' });
  } catch (error) {
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    // TODO: Implement POST handler
    return NextResponse.json({ message: 'POST {name}', data: body });
  } catch (error) {
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
""",
        },
        "express": {
            "path": "src/routes/{name}.ts",
            "content": """import { Router, Request, Response } from 'express';

const router = Router();

/**
 * GET /{name}
 */
router.get('/', async (req: Request, res: Response) => {
  try {
    // TODO: Implement GET handler
    res.json({ message: 'GET {name}' });
  } catch (error) {
    res.status(500).json({ error: 'Internal Server Error' });
  }
});

/**
 * POST /{name}
 */
router.post('/', async (req: Request, res: Response) => {
  try {
    const body = req.body;
    // TODO: Implement POST handler
    res.json({ message: 'POST {name}', data: body });
  } catch (error) {
    res.status(500).json({ error: 'Internal Server Error' });
  }
});

export default router;
""",
        },
        "fastapi": {
            "path": "app/routes/{name}.py",
            "content": '''"""
{name} API routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

router = APIRouter(prefix="/{name}", tags=["{name}"])


class {Name}Request(BaseModel):
    """Request model for {name}"""
    pass


class {Name}Response(BaseModel):
    """Response model for {name}"""
    message: str
    data: Dict[str, Any] = None


@router.get("/", response_model={Name}Response)
async def get_{name}():
    """GET /{name}"""
    # TODO: Implement GET handler
    return {Name}Response(message="GET {name}")


@router.post("/", response_model={Name}Response)
async def post_{name}(request: {Name}Request):
    """POST /{name}"""
    # TODO: Implement POST handler
    return {Name}Response(message="POST {name}", data=request.dict())
''',
        },
    },
    "component": {
        "react": {
            "path": "src/components/{Name}/{Name}.tsx",
            "content": """import React from 'react';
import styles from './{Name}.module.css';

interface {Name}Props {
  // TODO: Define props
}

export const {Name}: React.FC<{Name}Props> = (props) => {
  return (
    <div className={styles.container}>
      <h2>{Name} Component</h2>
      {/* TODO: Implement component */}
    </div>
  );
};

export default {Name};
""",
            "additional_files": {
                "src/components/{Name}/{Name}.module.css": """.container {
  /* TODO: Add styles */
}
""",
                "src/components/{Name}/index.ts": """export { {Name} } from './{Name}';
export { default } from './{Name}';
""",
            },
        },
        "nextjs": {
            "path": "components/{Name}/{Name}.tsx",
            "content": """'use client';

import React from 'react';
import styles from './{Name}.module.css';

interface {Name}Props {
  // TODO: Define props
}

export const {Name}: React.FC<{Name}Props> = (props) => {
  return (
    <div className={styles.container}>
      <h2>{Name} Component</h2>
      {/* TODO: Implement component */}
    </div>
  );
};

export default {Name};
""",
            "additional_files": {
                "components/{Name}/{Name}.module.css": """.container {
  /* TODO: Add styles */
}
""",
                "components/{Name}/index.ts": """export { {Name} } from './{Name}';
export { default } from './{Name}';
""",
            },
        },
        "vue": {
            "path": "src/components/{Name}.vue",
            "content": """<template>
  <div class="{name}-container">
    <h2>{Name} Component</h2>
    <!-- TODO: Implement component -->
  </div>
</template>

<script setup lang="ts">
// TODO: Define props and logic
interface Props {
}

const props = defineProps<Props>();
</script>

<style scoped>
.{name}-container {
  /* TODO: Add styles */
}
</style>
""",
        },
    },
    "page": {
        "nextjs": {
            "path": "app/{name}/page.tsx",
            "content": """import { Metadata } from 'next';

export const metadata: Metadata = {
  title: '{Name}',
  description: '{Name} page',
};

export default function {Name}Page() {
  return (
    <main>
      <h1>{Name}</h1>
      {/* TODO: Implement page */}
    </main>
  );
}
""",
        },
        "react": {
            "path": "src/pages/{Name}Page.tsx",
            "content": """import React from 'react';

export const {Name}Page: React.FC = () => {
  return (
    <main>
      <h1>{Name}</h1>
      {/* TODO: Implement page */}
    </main>
  );
};

export default {Name}Page;
""",
        },
    },
    "model": {
        "fastapi": {
            "path": "app/models/{name}.py",
            "content": '''"""
{Name} model and schema definitions
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base


class {Name}(Base):
    """SQLAlchemy model for {name}"""
    __tablename__ = "{name}s"

    id = Column(Integer, primary_key=True, index=True)
    # TODO: Add fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class {Name}Base(BaseModel):
    """Base Pydantic schema for {name}"""
    # TODO: Add fields
    pass


class {Name}Create({Name}Base):
    """Schema for creating {name}"""
    pass


class {Name}Update(BaseModel):
    """Schema for updating {name}"""
    # TODO: Add optional fields
    pass


class {Name}Response({Name}Base):
    """Schema for {name} response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
''',
        },
        "django": {
            "path": "app/models/{name}.py",
            "content": '''"""
{Name} model definition
"""
from django.db import models


class {Name}(models.Model):
    """{Name} model"""
    # TODO: Add fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "{name}"
        verbose_name_plural = "{name}s"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{Name} {{self.id}}"
''',
        },
        "prisma": {
            "path": "prisma/models/{name}.prisma",
            "content": """// {Name} model
// Add this to your schema.prisma file

model {Name} {{
  id        Int      @id @default(autoincrement())
  // TODO: Add fields
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}}
""",
        },
    },
    "service": {
        "express": {
            "path": "src/services/{name}Service.ts",
            "content": """/**
 * {Name} Service
 * Business logic for {name} operations
 */

export class {Name}Service {
  /**
   * Get all {name}s
   */
  async getAll(): Promise<any[]> {
    // TODO: Implement
    return [];
  }

  /**
   * Get {name} by ID
   */
  async getById(id: string): Promise<any | null> {
    // TODO: Implement
    return null;
  }

  /**
   * Create a new {name}
   */
  async create(data: any): Promise<any> {
    // TODO: Implement
    return data;
  }

  /**
   * Update {name}
   */
  async update(id: string, data: any): Promise<any | null> {
    // TODO: Implement
    return null;
  }

  /**
   * Delete {name}
   */
  async delete(id: string): Promise<boolean> {
    // TODO: Implement
    return false;
  }
}

export const {name}Service = new {Name}Service();
""",
        },
        "fastapi": {
            "path": "app/services/{name}_service.py",
            "content": '''"""
{Name} Service
Business logic for {name} operations
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.{name} import {Name}, {Name}Create, {Name}Update


class {Name}Service:
    """{Name} service class"""

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[{Name}]:
        """Get all {name}s"""
        return db.query({Name}).offset(skip).limit(limit).all()

    def get_by_id(self, db: Session, id: int) -> Optional[{Name}]:
        """Get {name} by ID"""
        return db.query({Name}).filter({Name}.id == id).first()

    def create(self, db: Session, data: {Name}Create) -> {Name}:
        """Create a new {name}"""
        db_obj = {Name}(**data.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, id: int, data: {Name}Update) -> Optional[{Name}]:
        """Update {name}"""
        db_obj = self.get_by_id(db, id)
        if not db_obj:
            return None

        for key, value in data.dict(exclude_unset=True).items():
            setattr(db_obj, key, value)

        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int) -> bool:
        """Delete {name}"""
        db_obj = self.get_by_id(db, id)
        if not db_obj:
            return False

        db.delete(db_obj)
        db.commit()
        return True


{name}_service = {Name}Service()
''',
        },
    },
    "test-suite": {
        "jest": {
            "path": "tests/{name}.test.ts",
            "content": """import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';

describe('{Name}', () => {
  beforeEach(() => {
    // Setup before each test
  });

  afterEach(() => {
    // Cleanup after each test
  });

  describe('feature 1', () => {
    it('should do something', () => {
      // TODO: Implement test
      expect(true).toBe(true);
    });

    it('should handle edge cases', () => {
      // TODO: Implement test
      expect(true).toBe(true);
    });
  });

  describe('feature 2', () => {
    it('should work correctly', () => {
      // TODO: Implement test
      expect(true).toBe(true);
    });
  });
});
""",
        },
        "pytest": {
            "path": "tests/test_{name}.py",
            "content": '''"""
Tests for {name}
"""
import pytest


class Test{Name}:
    """Test class for {Name}"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup before each test"""
        # TODO: Setup
        yield
        # TODO: Teardown

    def test_feature_1(self):
        """Test feature 1"""
        # TODO: Implement test
        assert True

    def test_feature_2(self):
        """Test feature 2"""
        # TODO: Implement test
        assert True

    def test_edge_cases(self):
        """Test edge cases"""
        # TODO: Implement test
        assert True


class Test{Name}Integration:
    """Integration tests for {Name}"""

    @pytest.mark.integration
    def test_integration(self):
        """Test integration"""
        # TODO: Implement test
        assert True
''',
        },
    },
    "auth": {
        "nextjs": {
            "path": "lib/auth.ts",
            "content": """/**
 * Authentication configuration
 * Using NextAuth.js for authentication
 */
import { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import GoogleProvider from 'next-auth/providers/google';
import GitHubProvider from 'next-auth/providers/github';

export const authOptions: NextAuthOptions = {
  providers: [
    // Credentials provider for email/password
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        // TODO: Implement credential validation
        // This is where you would verify against your database
        if (!credentials?.email || !credentials?.password) {
          return null;
        }

        // Example: verify user
        // const user = await db.user.findUnique({ where: { email: credentials.email } });
        // if (!user || !await bcrypt.compare(credentials.password, user.password)) {
        //   return null;
        // }
        // return user;

        return null;
      },
    }),
    // Google OAuth
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    // GitHub OAuth
    GitHubProvider({
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    }),
  ],
  pages: {
    signIn: '/auth/signin',
    signOut: '/auth/signout',
    error: '/auth/error',
  },
  callbacks: {
    async session({ session, token }) {
      // Add user ID to session
      if (token.sub) {
        session.user.id = token.sub;
      }
      return session;
    },
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
      }
      return token;
    },
  },
  session: {
    strategy: 'jwt',
  },
};
""",
            "additional_files": {
                "app/api/auth/[...nextauth]/route.ts": """import NextAuth from 'next-auth';
import { authOptions } from '@/lib/auth';

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
""",
                "middleware_ts": """import { withAuth } from 'next-auth/middleware';

export default withAuth({
  pages: {
    signIn: '/auth/signin',
  },
});

export const config = {
  matcher: [
    // Add protected routes here
    // '/dashboard/:path*',
    // '/api/protected/:path*',
  ],
};
""",
            },
        },
        "fastapi": {
            "path": "app/auth/auth.py",
            "content": '''"""
Authentication module for FastAPI
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Configuration
SECRET_KEY = "your-secret-key-here"  # TODO: Use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Token(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token payload data"""
    username: Optional[str] = None


class User(BaseModel):
    """User model"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get current user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    # TODO: Get user from database
    # user = db.get_user(username=token_data.username)
    # if user is None:
    #     raise credentials_exception
    # return user

    raise credentials_exception


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
''',
        },
    },
    "database": {
        "prisma": {
            "path": "prisma/schema.prisma",
            "content": """// Prisma Schema
// https://pris.ly/d/prisma-schema

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"  // or "mysql", "sqlite", "mongodb"
  url      = env("DATABASE_URL")
}

// User model
model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  name      String?
  password  String
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  // Relations
  // posts     Post[]
}

// Add your models below
""",
            "additional_files": {
                "lib/prisma.ts": """import { PrismaClient } from '@prisma/client';

declare global {
  var prisma: PrismaClient | undefined;
}

export const prisma = globalThis.prisma || new PrismaClient();

if (process.env.NODE_ENV !== 'production') {
  globalThis.prisma = prisma;
}

export default prisma;
""",
            },
        },
        "sqlalchemy": {
            "path": "app/database.py",
            "content": '''"""
Database configuration and session management
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
''',
        },
    },
}


# Stack recommendation rules
STACK_RECOMMENDATIONS = {
    "web_app": {
        "patterns": ["website", "web app", "dashboard", "portal", "admin panel"],
        "recommendation": {
            "frontend": "Next.js with TypeScript",
            "reasoning": "Server-side rendering, great DX, built-in routing, API routes",
            "alternatives": ["Vite + React", "Remix", "SvelteKit"],
        },
    },
    "api": {
        "patterns": ["api", "backend", "server", "microservice", "rest api", "graphql"],
        "recommendation": {
            "backend": "FastAPI (Python) or Express (Node.js)",
            "reasoning": "FastAPI for speed + type safety, Express for JavaScript ecosystem",
            "alternatives": ["NestJS", "Go + Chi", "Rust + Actix"],
        },
    },
    "saas": {
        "patterns": ["saas", "subscription", "b2b", "multi-tenant"],
        "recommendation": {
            "stack": "Next.js + Prisma + PostgreSQL + Stripe",
            "reasoning": "Full-stack with auth, payments, and database built-in patterns",
            "alternatives": ["Remix + Supabase", "Django + Stripe"],
        },
    },
    "mobile": {
        "patterns": ["mobile app", "ios", "android", "cross-platform"],
        "recommendation": {
            "framework": "React Native or Flutter",
            "reasoning": "React Native for JS devs, Flutter for performance",
            "alternatives": ["Expo", "Ionic", "Native development"],
        },
    },
    "cli": {
        "patterns": ["cli", "command line", "terminal tool"],
        "recommendation": {
            "language": "Go or Rust",
            "reasoning": "Single binary distribution, fast startup, no runtime needed",
            "alternatives": ["Python + Click", "Node.js + Commander"],
        },
    },
    "data": {
        "patterns": ["data pipeline", "etl", "analytics", "ml", "machine learning"],
        "recommendation": {
            "stack": "Python + Pandas/Polars + SQLAlchemy",
            "reasoning": "Rich data ecosystem, ML libraries, scientific computing",
            "alternatives": ["Apache Spark", "dbt + Snowflake"],
        },
    },
}


async def scaffold_project(
    context: Dict[str, Any],
    project_name: str,
    project_type: str,
    parent_directory: str,
    description: Optional[str] = None,
    typescript: bool = True,
    git_init: bool = True,
    install_dependencies: bool = True,
) -> ToolResult:
    """
    Scaffold a new project with the specified type and configuration.

    Args:
        project_name: Name of the project (will be used as directory name)
        project_type: Type of project (nextjs, react, vite, express, fastapi, etc.)
        parent_directory: Parent directory where project will be created
        description: Optional project description
        typescript: Use TypeScript (default True)
        git_init: Initialize git repository (default True)
        install_dependencies: Install dependencies after scaffolding (default True)

    Returns:
        ToolResult with scaffolding output and status
    """
    logger.info(
        "scaffold_project",
        project_name=project_name,
        project_type=project_type,
        parent_directory=parent_directory,
    )

    # Map project type to scaffolder enum
    project_type_lower = project_type.lower().strip()
    scaffolder_type = EXTENDED_PROJECT_TYPES.get(
        project_type_lower, ProjectType.UNKNOWN
    )

    # Create scaffolder instance
    scaffolder = ProjectScaffolder()

    # Build request
    request = ProjectScaffoldRequest(
        project_name=project_name,
        project_type=scaffolder_type,
        parent_directory=parent_directory,
        description=description,
        typescript=typescript,
        git_init=git_init,
        install_dependencies=install_dependencies,
    )

    # Execute scaffolding
    result = await scaffolder.scaffold_project(request)

    # Build output message
    lines = [f"## Project Scaffolding: {project_name}\n"]

    if result.success:
        lines.append("**Status**: Success")
        lines.append(f"**Path**: `{result.project_path}`")
        lines.append(f"**Type**: {result.project_type.value}")
        lines.append("\n**Commands Executed**:")
        for cmd in result.commands_run:
            lines.append(f"- `{cmd}`")

        lines.append("\n**Next Steps**:")
        lines.append(f"1. `cd {result.project_path}`")
        if not install_dependencies:
            lines.append("2. Install dependencies")
        lines.append("3. Start development server")
    else:
        lines.append("**Status**: Failed")
        lines.append(f"**Error**: {result.error}")
        lines.append(f"\n**Message**: {result.message}")

    return ToolResult(output="\n".join(lines), sources=[])


async def detect_requirements(
    context: Dict[str, Any],
    description: str,
) -> ToolResult:
    """
    Analyze a project description and recommend the optimal tech stack.

    Uses NLP analysis to understand requirements and suggest:
    - Frontend framework
    - Backend framework
    - Database
    - Deployment platform
    - Additional tools/services

    Args:
        description: Natural language description of the project

    Returns:
        ToolResult with stack recommendations
    """
    logger.info("detect_requirements", description=description[:100])

    description_lower = description.lower()

    # Find matching patterns
    matches = []
    for category, config in STACK_RECOMMENDATIONS.items():
        for pattern in config["patterns"]:
            if pattern in description_lower:
                matches.append((category, config))
                break

    # Build recommendation
    lines = ["## Tech Stack Recommendation\n"]
    lines.append(
        f"**Based on**: \"{description[:200]}{'...' if len(description) > 200 else ''}\"\n"
    )

    if not matches:
        # Generic web app recommendation
        lines.append("**Detected Type**: General Web Application\n")
        lines.append("**Recommended Stack**:")
        lines.append("- **Frontend**: Next.js with TypeScript")
        lines.append("- **Backend**: Next.js API Routes or FastAPI")
        lines.append("- **Database**: PostgreSQL with Prisma ORM")
        lines.append("- **Deployment**: Vercel or Railway")
        lines.append(
            "\n**Reasoning**: Modern, full-stack solution with excellent developer experience"
        )
    else:
        for category, config in matches:
            rec = config["recommendation"]
            lines.append(f"**Detected Type**: {category.replace('_', ' ').title()}\n")
            lines.append("**Recommended Stack**:")
            for key, value in rec.items():
                if key != "reasoning" and key != "alternatives":
                    lines.append(f"- **{key.title()}**: {value}")
            lines.append(f"\n**Reasoning**: {rec.get('reasoning', 'N/A')}")
            if rec.get("alternatives"):
                lines.append(f"\n**Alternatives**: {', '.join(rec['alternatives'])}")
            lines.append("")

    # Add deployment recommendations
    lines.append("\n### Deployment Options")
    if any("saas" in m[0] or "web" in m[0] for m in matches) or not matches:
        lines.append("- **Vercel**: Best for Next.js/React apps")
        lines.append("- **Railway**: Great for full-stack with databases")
        lines.append("- **Fly.io**: Edge deployment, good for APIs")
    if any("api" in m[0] or "backend" in m[0] for m in matches):
        lines.append("- **Railway**: Easy database provisioning")
        lines.append("- **Render**: Simple Docker deployments")
        lines.append("- **AWS Lambda**: Serverless APIs")

    # Add tooling recommendations
    lines.append("\n### Recommended Tooling")
    lines.append("- **Version Control**: Git + GitHub")
    lines.append("- **CI/CD**: GitHub Actions")
    lines.append("- **Monitoring**: Sentry for errors, Datadog for APM")
    lines.append("- **Testing**: Jest/Vitest (JS) or pytest (Python)")

    return ToolResult(output="\n".join(lines), sources=[])


async def add_feature_scaffold(
    context: Dict[str, Any],
    workspace_path: str,
    feature_type: str,
    feature_name: str,
) -> ToolResult:
    """
    Add a feature scaffold to an existing project.

    Detects the project framework and generates appropriate boilerplate.

    Args:
        workspace_path: Path to the project root
        feature_type: Type of feature (api-route, component, page, model, service, test-suite, auth, database)
        feature_name: Name of the feature

    Returns:
        ToolResult with created files and next steps
    """
    logger.info(
        "add_feature_scaffold",
        workspace_path=workspace_path,
        feature_type=feature_type,
        feature_name=feature_name,
    )

    # Detect project framework
    framework = _detect_project_framework(workspace_path)

    if not framework:
        return ToolResult(
            output=f"Could not detect project framework in: {workspace_path}\n\n"
            f"Please ensure you're in a valid project directory with package.json, "
            f"requirements.txt, or similar configuration files.",
            sources=[],
        )

    # Get template for feature type and framework
    templates = FEATURE_TEMPLATES.get(feature_type, {})
    template = templates.get(framework)

    # Try fallback frameworks
    if not template:
        fallback_map = {
            "nextjs": "react",
            "vite-react": "react",
            "express": "express",
            "nestjs": "express",
            "fastapi": "fastapi",
            "flask": "fastapi",
            "django": "django",
        }
        fallback = fallback_map.get(framework)
        if fallback:
            template = templates.get(fallback)

    if not template:
        available_features = list(FEATURE_TEMPLATES.keys())
        return ToolResult(
            output=f"No template available for '{feature_type}' in {framework} projects.\n\n"
            f"Available feature types: {', '.join(available_features)}\n"
            f"Try a different feature type or create the files manually.",
            sources=[],
        )

    # Process template with feature name
    created_files = []

    # Generate name variants
    name_lower = feature_name.lower().replace(" ", "_").replace("-", "_")
    feature_name.lower().replace(" ", "-").replace("_", "-")
    name_pascal = "".join(
        word.capitalize() for word in re.split(r"[-_\s]", feature_name)
    )

    # Main file
    main_path = template["path"].format(
        name=name_lower,
        Name=name_pascal,
    )
    main_content = template["content"].format(
        name=name_lower,
        Name=name_pascal,
    )

    full_main_path = os.path.join(workspace_path, main_path)
    os.makedirs(os.path.dirname(full_main_path), exist_ok=True)

    with open(full_main_path, "w") as f:
        f.write(main_content)
    created_files.append(main_path)

    # Additional files
    additional = template.get("additional_files", {})
    for file_path, content in additional.items():
        formatted_path = file_path.format(name=name_lower, Name=name_pascal)
        formatted_content = content.format(name=name_lower, Name=name_pascal)

        full_path = os.path.join(workspace_path, formatted_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w") as f:
            f.write(formatted_content)
        created_files.append(formatted_path)

    # Build output
    lines = [f"## Feature Scaffold: {feature_type}\n"]
    lines.append(f"**Feature Name**: {feature_name}")
    lines.append(f"**Framework**: {framework}")
    lines.append("\n**Created Files**:")
    for file in created_files:
        lines.append(f"- `{file}`")

    lines.append("\n**Next Steps**:")
    lines.append("1. Review and customize the generated code")
    lines.append("2. Add your business logic")
    if feature_type == "api-route":
        lines.append("3. Test the endpoint")
    elif feature_type == "component":
        lines.append("3. Import and use the component")
    elif feature_type == "model":
        lines.append("3. Run database migrations")
    elif feature_type == "auth":
        lines.append("3. Set up environment variables for OAuth providers")

    return ToolResult(output="\n".join(lines), sources=[])


async def list_scaffold_templates(
    context: Dict[str, Any],
) -> ToolResult:
    """
    List all available scaffolding templates.

    Returns:
        ToolResult with available project types and feature templates
    """
    lines = ["## Available Scaffolding Templates\n"]

    # Project types
    lines.append("### Project Types")
    lines.append("Use with `scaffold.project`:\n")

    project_types = {
        "nextjs": "Full-stack React framework with SSR/SSG",
        "react": "React SPA with Create React App",
        "vite-react": "React with Vite bundler",
        "vite-vue": "Vue.js with Vite bundler",
        "express": "Express.js API server",
        "fastapi": "Python FastAPI server",
        "flask": "Python Flask server",
        "django": "Python Django full-stack",
        "python": "Basic Python project",
        "static-html": "Static HTML website",
        "go": "Go project",
        "rust": "Rust project",
    }

    for name, desc in project_types.items():
        lines.append(f"- **{name}**: {desc}")

    # Feature types
    lines.append("\n### Feature Types")
    lines.append("Use with `scaffold.add_feature`:\n")

    for feature_type, frameworks in FEATURE_TEMPLATES.items():
        supported = ", ".join(frameworks.keys())
        lines.append(f"- **{feature_type}**: Supported in {supported}")

    # Usage examples
    lines.append("\n### Usage Examples")
    lines.append("```")
    lines.append("# Create a new Next.js project")
    lines.append('scaffold.project(name="my-app", type="nextjs", parent="/projects")')
    lines.append("")
    lines.append("# Add an API route to existing project")
    lines.append(
        'scaffold.add_feature(workspace="/path/to/project", type="api-route", name="users")'
    )
    lines.append("")
    lines.append("# Detect optimal stack from description")
    lines.append(
        'scaffold.detect_requirements(description="SaaS app with user auth and payments")'
    )
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


def _detect_project_framework(workspace_path: str) -> Optional[str]:
    """Detect the framework used in a project directory."""

    # Check package.json for Node.js projects
    package_json_path = os.path.join(workspace_path, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "next" in deps:
                    return "nextjs"
                if "vue" in deps:
                    return "vue"
                if "svelte" in deps:
                    return "svelte"
                if "@angular/core" in deps:
                    return "angular"
                if "react" in deps:
                    if "vite" in deps:
                        return "vite-react"
                    return "react"
                if "express" in deps:
                    return "express"
                if "@nestjs/core" in deps:
                    return "nestjs"

                return "node"
        except (json.JSONDecodeError, IOError):
            pass

    # Check for Python projects
    if os.path.exists(os.path.join(workspace_path, "requirements.txt")):
        try:
            with open(os.path.join(workspace_path, "requirements.txt"), "r") as f:
                content = f.read().lower()
                if "fastapi" in content:
                    return "fastapi"
                if "flask" in content:
                    return "flask"
                if "django" in content:
                    return "django"
                return "python"
        except IOError:
            return "python"

    if os.path.exists(os.path.join(workspace_path, "pyproject.toml")):
        return "python"

    # Check for manage.py (Django)
    if os.path.exists(os.path.join(workspace_path, "manage.py")):
        return "django"

    # Check for Go
    if os.path.exists(os.path.join(workspace_path, "go.mod")):
        return "go"

    # Check for Rust
    if os.path.exists(os.path.join(workspace_path, "Cargo.toml")):
        return "rust"

    return None


# Export tools for the agent dispatcher
SCAFFOLDING_TOOLS = {
    "scaffold_project": scaffold_project,
    "scaffold_detect_requirements": detect_requirements,
    "scaffold_add_feature": add_feature_scaffold,
    "scaffold_list_templates": list_scaffold_templates,
}
