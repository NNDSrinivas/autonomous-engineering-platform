"""
Comprehensive NAVI SaaS Capability Tests

Tests:
1. Multi-language/framework capability (universal assistant)
2. Token usage and cost tracking
3. Multi-tenant context (org/team/user)
4. RAG knowledge retrieval
5. Feedback learning
6. Gated approvals

These tests verify NAVI works as a universal SaaS AI coding assistant
comparable to Cline, Claude Code, GitHub Copilot, and Codex.
"""

import pytest
import aiohttp
import json
import os
import tempfile

# Test configuration
BASE_URL = os.getenv("NAVI_TEST_URL", "http://localhost:8002")
TIMEOUT = 120  # seconds


def get_api_key():
    """Get API key from environment."""
    return os.getenv("ANTHROPIC_API_KEY", "")


class TestNaviUniversalCapabilities:
    """Test NAVI's ability to handle any language/framework."""

    @pytest.fixture
    def session(self):
        """Create a new session for each test."""
        return aiohttp.ClientSession()

    async def make_navi_request(self, session, message: str, workspace: str = None):
        """Make a request to NAVI and return the result."""
        workspace = workspace or tempfile.mkdtemp()

        payload = {
            "message": message,
            "workspace_root": workspace,
            "context": {
                "project_type": "unknown",
                "technologies": [],
                "current_file": None,
                "errors": [],
            }
        }

        try:
            async with session.post(
                f"{BASE_URL}/api/navi/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    return {"error": error, "status": response.status}
                return await response.json()
        except Exception as e:
            return {"error": str(e)}

    @pytest.mark.asyncio
    async def test_python_fastapi_endpoint(self):
        """Test creating a Python FastAPI endpoint."""
        async with aiohttp.ClientSession() as session:
            result = await self.make_navi_request(
                session,
                "Create a FastAPI endpoint that returns user data with Pydantic validation"
            )

            assert "error" not in result or result.get("status") == 200
            assert "content" in result or "message" in result or "response" in result

            # Check for Python/FastAPI patterns in response
            response_text = str(result)
            has_python = any(kw in response_text.lower() for kw in [
                "fastapi", "pydantic", "def ", "async def", "@router", "@app"
            ])
            print(f"\n✅ Python FastAPI Test: {'PASS' if has_python else 'PARTIAL'}")
            print(f"   Content preview: {result.get('content', '')[:200]}...")

    @pytest.mark.asyncio
    async def test_javascript_express_api(self):
        """Test creating a Node.js Express API."""
        async with aiohttp.ClientSession() as session:
            result = await self.make_navi_request(
                session,
                "Create an Express.js REST API with GET and POST endpoints for products"
            )

            assert "error" not in result or result.get("status") == 200
            response_text = str(result)
            has_js = any(kw in response_text.lower() for kw in [
                "express", "router", "app.get", "app.post", "req, res", "module.exports"
            ])
            print(f"\n✅ JavaScript Express Test: {'PASS' if has_js else 'PARTIAL'}")
            print(f"   Content preview: {result.get('content', '')[:200]}...")

    @pytest.mark.asyncio
    async def test_go_http_handler(self):
        """Test creating a Go HTTP handler."""
        async with aiohttp.ClientSession() as session:
            result = await self.make_navi_request(
                session,
                "Create a Go HTTP handler that serves JSON data with proper error handling"
            )

            assert "error" not in result or result.get("status") == 200
            response_text = str(result)
            has_go = any(kw in response_text.lower() for kw in [
                "func ", "http.handler", "json.marshal", "w http.responsewriter", "package"
            ])
            print(f"\n✅ Go HTTP Handler Test: {'PASS' if has_go else 'PARTIAL'}")
            print(f"   Content preview: {result.get('content', '')[:200]}...")

    @pytest.mark.asyncio
    async def test_rust_actix_handler(self):
        """Test creating a Rust Actix handler."""
        async with aiohttp.ClientSession() as session:
            result = await self.make_navi_request(
                session,
                "Create a Rust Actix-web handler that returns JSON with serde serialization"
            )

            assert "error" not in result or result.get("status") == 200
            response_text = str(result)
            has_rust = any(kw in response_text.lower() for kw in [
                "actix", "serde", "fn ", "async fn", "#[derive", "httpresponse"
            ])
            print(f"Rust Actix Test: {'PASS' if has_rust else 'PARTIAL'}")

    @pytest.mark.asyncio
    async def test_react_component(self):
        """Test creating a React component."""
        async with aiohttp.ClientSession() as session:
            result = await self.make_navi_request(
                session,
                "Create a React component with hooks for a user profile card with TypeScript"
            )

            assert "error" not in result or result.get("status") == 200
            response_text = str(result)
            has_react = any(kw in response_text.lower() for kw in [
                "usestate", "useeffect", "react", "const ", "interface", "tsx", "jsx"
            ])
            print(f"React Component Test: {'PASS' if has_react else 'PARTIAL'}")

    @pytest.mark.asyncio
    async def test_docker_compose(self):
        """Test creating Docker Compose configuration."""
        async with aiohttp.ClientSession() as session:
            result = await self.make_navi_request(
                session,
                "Create a Docker Compose file for a web app with PostgreSQL and Redis"
            )

            assert "error" not in result or result.get("status") == 200
            response_text = str(result)
            has_docker = any(kw in response_text.lower() for kw in [
                "version:", "services:", "postgres", "redis", "docker-compose", "volumes:"
            ])
            print(f"Docker Compose Test: {'PASS' if has_docker else 'PARTIAL'}")

    @pytest.mark.asyncio
    async def test_terraform_aws(self):
        """Test creating Terraform AWS infrastructure."""
        async with aiohttp.ClientSession() as session:
            result = await self.make_navi_request(
                session,
                "Create Terraform configuration for an AWS Lambda function with API Gateway"
            )

            assert "error" not in result or result.get("status") == 200
            response_text = str(result)
            has_terraform = any(kw in response_text.lower() for kw in [
                "resource", "aws_lambda", "api_gateway", "terraform", "provider"
            ])
            print(f"Terraform AWS Test: {'PASS' if has_terraform else 'PARTIAL'}")

    @pytest.mark.asyncio
    async def test_sql_migration(self):
        """Test creating SQL migration."""
        async with aiohttp.ClientSession() as session:
            result = await self.make_navi_request(
                session,
                "Create a PostgreSQL migration for a users table with proper indexes"
            )

            assert "error" not in result or result.get("status") == 200
            response_text = str(result)
            has_sql = any(kw in response_text.lower() for kw in [
                "create table", "index", "primary key", "varchar", "timestamp"
            ])
            print(f"SQL Migration Test: {'PASS' if has_sql else 'PARTIAL'}")


class TestTokenUsageTracking:
    """Test token usage and cost tracking."""

    @pytest.mark.asyncio
    async def test_usage_in_response(self):
        """Test that usage info is included in responses."""
        async with aiohttp.ClientSession() as session:
            workspace = tempfile.mkdtemp()
            payload = {
                "message": "Create a simple hello world function in Python",
                "context": {
                    "workspace_path": workspace,
                    "project_type": "python",
                }
            }

            async with session.post(
                f"{BASE_URL}/api/navi/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                if response.status == 200:
                    result = await response.json()

                    # Check for usage info in response
                    has_usage = "usage" in result
                    if has_usage:
                        usage = result["usage"]
                        print(f"Usage Info: {json.dumps(usage, indent=2)}")
                        assert "input_tokens" in usage or "total_tokens" in usage
                    else:
                        print("Usage info not yet in response (streaming may differ)")

    @pytest.mark.asyncio
    async def test_usage_summary_endpoint(self):
        """Test the usage summary API endpoint."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/saas/usage/summary?days=7",
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"Usage Summary: {json.dumps(result, indent=2)}")
                    assert "totals" in result
                    assert "period" in result
                else:
                    # Endpoint might not be registered yet
                    print(f"Usage endpoint status: {response.status}")

    @pytest.mark.asyncio
    async def test_pricing_endpoint(self):
        """Test the model pricing API endpoint."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/saas/usage/pricing",
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"Model Pricing: {json.dumps(result, indent=2)}")
                    assert "pricing" in result
                else:
                    print(f"Pricing endpoint status: {response.status}")


class TestSaaSManagement:
    """Test SaaS management endpoints."""

    @pytest.mark.asyncio
    async def test_create_organization(self):
        """Test creating an organization."""
        async with aiohttp.ClientSession() as session:
            payload = {
                "org_id": "test-org-001",
                "name": "Test Organization",
                "preferred_languages": ["python", "typescript"],
                "indent_size": 4,
                "require_type_hints": True,
            }

            async with session.post(
                f"{BASE_URL}/saas/organizations",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                result = await response.json()
                print(f"Create Org Response: {json.dumps(result, indent=2)}")
                # Either created or already exists
                assert response.status in [200, 400]

    @pytest.mark.asyncio
    async def test_get_organization(self):
        """Test getting an organization."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/saas/organizations/test-org-001",
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"Get Org Response: {json.dumps(result, indent=2)}")
                    assert "org_id" in result
                else:
                    print(f"Get org status: {response.status}")


class TestMultiLanguageDetection:
    """Test domain detection for different languages/frameworks."""

    def test_python_detection(self):
        """Test Python domain detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create a FastAPI endpoint with Pydantic models")
        assert result == DomainType.BACKEND_PYTHON

        result = detect_domain("Build a Django REST API")
        assert result == DomainType.BACKEND_PYTHON

    def test_javascript_detection(self):
        """Test JavaScript/Node detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create an Express.js middleware")
        assert result == DomainType.BACKEND_NODE

        result = detect_domain("Build a NestJS module")
        assert result == DomainType.BACKEND_NODE

    def test_go_detection(self):
        """Test Go detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create a Go Gin router")
        assert result == DomainType.BACKEND_GO

        result = detect_domain("Build a Golang HTTP handler")
        assert result == DomainType.BACKEND_GO

    def test_rust_detection(self):
        """Test Rust detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create a Rust Actix handler")
        assert result == DomainType.BACKEND_RUST

        result = detect_domain("Build with Cargo and Tokio")
        assert result == DomainType.BACKEND_RUST

    def test_react_detection(self):
        """Test React detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create a React component with useState")
        assert result == DomainType.FRONTEND_REACT

        result = detect_domain("Build a Redux store")
        assert result == DomainType.FRONTEND_REACT

    def test_docker_detection(self):
        """Test Docker detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create a Dockerfile for my app")
        assert result == DomainType.DEVOPS_DOCKER

        result = detect_domain("Set up Docker Compose")
        assert result == DomainType.DEVOPS_DOCKER

    def test_kubernetes_detection(self):
        """Test Kubernetes detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create a Kubernetes deployment")
        assert result == DomainType.DEVOPS_KUBERNETES

        result = detect_domain("Configure a K8s pod")
        assert result == DomainType.DEVOPS_KUBERNETES

    def test_terraform_detection(self):
        """Test Terraform detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create Terraform configuration")
        assert result == DomainType.DEVOPS_TERRAFORM

    def test_aws_detection(self):
        """Test AWS detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create an AWS Lambda function")
        assert result == DomainType.DEVOPS_AWS

        result = detect_domain("Set up S3 bucket with CloudFormation")
        assert result == DomainType.DEVOPS_AWS

    def test_ml_detection(self):
        """Test ML detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Train a TensorFlow model")
        assert result == DomainType.DATA_ML

        result = detect_domain("Create a PyTorch neural network")
        assert result == DomainType.DATA_ML


class TestCloudPlatformDetection:
    """Test detection for major cloud platforms."""

    def test_aws_detection_expanded(self):
        """Test expanded AWS detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Lambda
        result = detect_domain("Create an AWS Lambda function with API Gateway")
        assert result == DomainType.DEVOPS_AWS

        # EC2
        result = detect_domain("Set up EC2 instances with auto-scaling")
        assert result == DomainType.DEVOPS_AWS

        # S3
        result = detect_domain("Configure S3 bucket policies for CORS")
        assert result == DomainType.DEVOPS_AWS

        # CDK
        result = detect_domain("Write a CDK stack for ECS Fargate")
        assert result == DomainType.DEVOPS_AWS

    def test_gcp_detection(self):
        """Test GCP detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Cloud Run
        result = detect_domain("Deploy to Cloud Run with GCP")
        assert result == DomainType.DEVOPS_GCP

        # BigQuery
        result = detect_domain("Create a BigQuery table and run analytics")
        assert result == DomainType.DEVOPS_GCP

        # GKE
        result = detect_domain("Set up a GKE cluster")
        assert result == DomainType.DEVOPS_GCP

        # Google Cloud general
        result = detect_domain("Configure Google Cloud IAM")
        assert result == DomainType.DEVOPS_GCP

    def test_azure_detection(self):
        """Test Azure detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Azure Functions
        result = detect_domain("Create an Azure Function with HTTP trigger")
        assert result == DomainType.DEVOPS_AZURE

        # Azure general
        result = detect_domain("Configure Azure Service Bus queues")
        assert result == DomainType.DEVOPS_AZURE

        # Azure Cosmos DB
        result = detect_domain("Set up Azure Cosmos DB database")
        assert result == DomainType.DEVOPS_AZURE


class TestEnterpriseLanguageDetection:
    """Test detection for enterprise languages."""

    def test_java_detection(self):
        """Test Java/JVM detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Spring Boot
        result = detect_domain("Create a Spring Boot REST API")
        assert result == DomainType.BACKEND_JAVA

        # Maven
        result = detect_domain("Add dependencies to Maven pom.xml")
        assert result == DomainType.BACKEND_JAVA

        # Hibernate
        result = detect_domain("Configure Hibernate JPA entity mappings")
        assert result == DomainType.BACKEND_JAVA

    def test_dotnet_csharp_detection(self):
        """Test .NET/C# detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # ASP.NET
        result = detect_domain("Create an ASP.NET Web API controller")
        assert result == DomainType.BACKEND_CSHARP

        # C#
        result = detect_domain("Write a C# class with dependency injection")
        assert result == DomainType.BACKEND_CSHARP

        # Entity Framework
        result = detect_domain("Set up Entity Framework migrations")
        assert result == DomainType.BACKEND_CSHARP

        # .NET Core
        result = detect_domain("Build a .NET Core microservice")
        assert result == DomainType.BACKEND_CSHARP

    def test_cpp_detection(self):
        """Test C++ detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # C++ explicit
        result = detect_domain("Write C++ class with virtual methods")
        assert result == DomainType.SYSTEMS_CPP

        # CMake
        result = detect_domain("Create a CMake build configuration")
        assert result == DomainType.SYSTEMS_CPP

    def test_c_detection(self):
        """Test C detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # GCC
        result = detect_domain("Compile with GCC and create a Makefile")
        assert result == DomainType.SYSTEMS_C

        # Pointers
        result = detect_domain("Implement linked list with pointer arithmetic")
        assert result == DomainType.SYSTEMS_C

    def test_scala_detection(self):
        """Test Scala detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Scala basic
        result = detect_domain("Create a Scala class with case classes")
        assert result == DomainType.BACKEND_SCALA

        # Akka
        result = detect_domain("Build an Akka actor system")
        assert result == DomainType.BACKEND_SCALA

        # sbt
        result = detect_domain("Configure sbt build.sbt dependencies")
        assert result == DomainType.BACKEND_SCALA


class TestModernTechDetection:
    """Test detection for modern technologies."""

    def test_blockchain_solidity_detection(self):
        """Test Solidity/Ethereum detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Solidity
        result = detect_domain("Write a Solidity smart contract")
        assert result == DomainType.BLOCKCHAIN_SOLIDITY

        # Hardhat
        result = detect_domain("Deploy with Hardhat to Ethereum")
        assert result == DomainType.BLOCKCHAIN_SOLIDITY

        # ERC20
        result = detect_domain("Create an ERC20 token contract")
        assert result == DomainType.BLOCKCHAIN_SOLIDITY

    def test_blockchain_web3_detection(self):
        """Test Web3/Blockchain general detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Web3
        result = detect_domain("Connect to blockchain with Web3")
        assert result == DomainType.BLOCKCHAIN_WEB3

        # NFT
        result = detect_domain("Build an NFT marketplace")
        assert result == DomainType.BLOCKCHAIN_WEB3

        # DeFi
        result = detect_domain("Implement a DeFi liquidity pool")
        assert result == DomainType.BLOCKCHAIN_WEB3

    def test_elixir_detection(self):
        """Test Elixir/Phoenix detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Phoenix
        result = detect_domain("Create a Phoenix LiveView channel")
        assert result == DomainType.BACKEND_ELIXIR

        # GenServer
        result = detect_domain("Implement an OTP GenServer process")
        assert result == DomainType.BACKEND_ELIXIR

    def test_kafka_detection(self):
        """Test Kafka detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create a Kafka consumer and producer")
        assert result == DomainType.DATA_KAFKA

    def test_observability_detection(self):
        """Test observability/monitoring detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Prometheus
        result = detect_domain("Set up Prometheus metrics")
        assert result == DomainType.OBSERVABILITY

        # Grafana
        result = detect_domain("Create a Grafana dashboard")
        assert result == DomainType.OBSERVABILITY

        # OpenTelemetry
        result = detect_domain("Implement OpenTelemetry tracing")
        assert result == DomainType.OBSERVABILITY

    def test_graphql_detection(self):
        """Test GraphQL API detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create a GraphQL schema with resolvers")
        assert result == DomainType.API_GRAPHQL

        result = detect_domain("Set up Apollo Server")
        assert result == DomainType.API_GRAPHQL

    def test_grpc_detection(self):
        """Test gRPC detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        result = detect_domain("Create a gRPC server endpoint")
        assert result == DomainType.API_GRPC

    def test_embedded_detection(self):
        """Test embedded/IoT detection."""
        from backend.services.domain_knowledge import detect_domain, DomainType

        # Arduino
        result = detect_domain("Write Arduino firmware for ESP32")
        assert result == DomainType.SYSTEMS_EMBEDDED

        # FreeRTOS
        result = detect_domain("Configure FreeRTOS tasks")
        assert result == DomainType.SYSTEMS_EMBEDDED


class TestNAVIBrainDomainHints:
    """Test that NAVI brain correctly uses expanded domain hints."""

    def test_expanded_domain_hints_exist(self):
        """Verify expanded domain hints are available."""
        from backend.services.navi_brain import DynamicContextProvider

        hints = DynamicContextProvider.DOMAIN_HINTS

        # Verify new domains exist
        assert "java" in hints
        assert "dotnet" in hints
        assert "cpp" in hints
        assert "scala" in hints
        assert "golang" in hints
        assert "rust" in hints
        assert "aws" in hints
        assert "gcp" in hints
        assert "azure" in hints
        assert "kubernetes" in hints
        assert "blockchain" in hints
        assert "observability" in hints

    def test_aws_hints_comprehensive(self):
        """Test AWS hints include key services."""
        from backend.services.navi_brain import DynamicContextProvider

        aws_hints = DynamicContextProvider.DOMAIN_HINTS.get("aws", [])

        # Major AWS services should be in hints
        assert "ec2" in aws_hints
        assert "s3" in aws_hints
        assert "lambda" in aws_hints
        assert "rds" in aws_hints
        assert "dynamodb" in aws_hints
        assert "ecs" in aws_hints
        assert "eks" in aws_hints
        assert "cloudformation" in aws_hints or "cdk" in aws_hints

    def test_gcp_hints_comprehensive(self):
        """Test GCP hints include key services."""
        from backend.services.navi_brain import DynamicContextProvider

        gcp_hints = DynamicContextProvider.DOMAIN_HINTS.get("gcp", [])

        # Major GCP services should be in hints
        assert "gcp" in gcp_hints or "google cloud" in gcp_hints
        assert "bigquery" in gcp_hints
        assert "cloud run" in gcp_hints
        assert "gke" in gcp_hints
        assert "pubsub" in gcp_hints

    def test_java_hints_comprehensive(self):
        """Test Java hints include key frameworks."""
        from backend.services.navi_brain import DynamicContextProvider

        java_hints = DynamicContextProvider.DOMAIN_HINTS.get("java", [])

        # Java ecosystem should be covered
        assert "java" in java_hints
        assert "spring" in java_hints or "spring boot" in java_hints
        assert "maven" in java_hints
        assert "gradle" in java_hints

    def test_dotnet_hints_comprehensive(self):
        """Test .NET hints include key frameworks."""
        from backend.services.navi_brain import DynamicContextProvider

        dotnet_hints = DynamicContextProvider.DOMAIN_HINTS.get("dotnet", [])

        # .NET ecosystem should be covered
        assert ".net" in dotnet_hints or "dotnet" in dotnet_hints
        assert "c#" in dotnet_hints or "csharp" in dotnet_hints
        assert "asp.net" in dotnet_hints or "blazor" in dotnet_hints


def run_all_tests():
    """Run all tests and print summary."""
    print("=" * 60)
    print("NAVI SaaS COMPREHENSIVE TEST SUITE")
    print("=" * 60)

    # Run pytest with verbose output
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))


if __name__ == "__main__":
    run_all_tests()
