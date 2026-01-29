"""
Database tools for NAVI agent.

Provides tools for database schema design and management:
- Schema design from natural language
- Migration generation
- Seed data generation
- Schema analysis
- ERD generation

Works dynamically with multiple databases and ORMs.
"""

import os
import re
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

from backend.services.connector_base import ToolResult
from backend.services.database_executor_service import (
    database_executor_service,
    MigrationDirection,
)
from backend.services.execution_confirmation_service import (
    execution_confirmation_service,
    RiskLevel,
    OperationCategory,
)

logger = structlog.get_logger(__name__)


# ORM templates for different frameworks
ORM_TEMPLATES = {
    "prisma": {
        "model": """model {name} {{
  id        Int      @id @default(autoincrement())
{fields}
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
{relations}
}}
""",
        "field_types": {
            "string": "String",
            "text": "String",
            "int": "Int",
            "integer": "Int",
            "float": "Float",
            "decimal": "Decimal",
            "boolean": "Boolean",
            "bool": "Boolean",
            "datetime": "DateTime",
            "date": "DateTime",
            "json": "Json",
            "uuid": "String @default(uuid())",
        },
        "relation_one": "  {field}   {model}?  @relation(fields: [{field}Id], references: [id])\n  {field}Id Int?",
        "relation_many": "  {field} {model}[]",
    },
    "drizzle": {
        "model": """export const {name_lower} = pgTable("{name_plural}", {{
  id: serial("id").primaryKey(),
{fields}
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
}});

export type {name} = typeof {name_lower}.$inferSelect;
export type New{name} = typeof {name_lower}.$inferInsert;
""",
        "field_types": {
            "string": 'varchar("{field}", {{ length: 255 }})',
            "text": 'text("{field}")',
            "int": 'integer("{field}")',
            "integer": 'integer("{field}")',
            "float": 'real("{field}")',
            "decimal": 'decimal("{field}", {{ precision: 10, scale: 2 }})',
            "boolean": 'boolean("{field}")',
            "bool": 'boolean("{field}")',
            "datetime": 'timestamp("{field}")',
            "date": 'timestamp("{field}")',
            "json": 'jsonb("{field}")',
            "uuid": 'uuid("{field}").defaultRandom()',
        },
    },
    "sqlalchemy": {
        "model": '''class {name}(Base):
    """
    {name} model
    """
    __tablename__ = "{name_lower}s"

    id = Column(Integer, primary_key=True, index=True)
{fields}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
{relations}

    def __repr__(self):
        return f"<{name}(id={{self.id}})>"
''',
        "field_types": {
            "string": "Column(String(255))",
            "text": "Column(Text)",
            "int": "Column(Integer)",
            "integer": "Column(Integer)",
            "float": "Column(Float)",
            "decimal": "Column(Numeric(10, 2))",
            "boolean": "Column(Boolean, default=False)",
            "bool": "Column(Boolean, default=False)",
            "datetime": "Column(DateTime)",
            "date": "Column(Date)",
            "json": "Column(JSON)",
            "uuid": "Column(UUID(as_uuid=True), default=uuid.uuid4)",
        },
        "relation_one": '    {field}_id = Column(Integer, ForeignKey("{model_lower}s.id"))\n    {field} = relationship("{model}", back_populates="{name_lower}s")',
        "relation_many": '    {field} = relationship("{model}", back_populates="{name_lower}")',
    },
    "typeorm": {
        "model": """@Entity("{name_lower}s")
export class {name} {{
  @PrimaryGeneratedColumn()
  id: number;

{fields}

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
{relations}
}}
""",
        "field_types": {
            "string": "@Column({{ length: 255 }})\n  {field}: string;",
            "text": "@Column('text')\n  {field}: string;",
            "int": "@Column()\n  {field}: number;",
            "integer": "@Column()\n  {field}: number;",
            "float": "@Column('float')\n  {field}: number;",
            "decimal": "@Column('decimal', {{ precision: 10, scale: 2 }})\n  {field}: number;",
            "boolean": "@Column({{ default: false }})\n  {field}: boolean;",
            "bool": "@Column({{ default: false }})\n  {field}: boolean;",
            "datetime": "@Column()\n  {field}: Date;",
            "date": "@Column('date')\n  {field}: Date;",
            "json": "@Column('jsonb')\n  {field}: any;",
            "uuid": "@Column('uuid', {{ default: () => 'uuid_generate_v4()' }})\n  {field}: string;",
        },
    },
    "django": {
        "model": '''class {name}(models.Model):
    """
    {name} model
    """
{fields}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "{name_lower}"
        verbose_name_plural = "{name_lower}s"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{name} {{self.id}}"
''',
        "field_types": {
            "string": "models.CharField(max_length=255)",
            "text": "models.TextField()",
            "int": "models.IntegerField()",
            "integer": "models.IntegerField()",
            "float": "models.FloatField()",
            "decimal": "models.DecimalField(max_digits=10, decimal_places=2)",
            "boolean": "models.BooleanField(default=False)",
            "bool": "models.BooleanField(default=False)",
            "datetime": "models.DateTimeField()",
            "date": "models.DateField()",
            "json": "models.JSONField()",
            "uuid": "models.UUIDField(default=uuid.uuid4, editable=False)",
        },
        "relation_one": '    {field} = models.ForeignKey("{model}", on_delete=models.CASCADE, related_name="{name_lower}s")',
        "relation_many": "    # See {model} model for reverse relation",
    },
}

# SQL type mappings
SQL_TYPES = {
    "postgresql": {
        "string": "VARCHAR(255)",
        "text": "TEXT",
        "int": "INTEGER",
        "integer": "INTEGER",
        "float": "REAL",
        "decimal": "DECIMAL(10,2)",
        "boolean": "BOOLEAN",
        "bool": "BOOLEAN",
        "datetime": "TIMESTAMP",
        "date": "DATE",
        "json": "JSONB",
        "uuid": "UUID",
    },
    "mysql": {
        "string": "VARCHAR(255)",
        "text": "TEXT",
        "int": "INT",
        "integer": "INT",
        "float": "FLOAT",
        "decimal": "DECIMAL(10,2)",
        "boolean": "TINYINT(1)",
        "bool": "TINYINT(1)",
        "datetime": "DATETIME",
        "date": "DATE",
        "json": "JSON",
        "uuid": "CHAR(36)",
    },
    "sqlite": {
        "string": "TEXT",
        "text": "TEXT",
        "int": "INTEGER",
        "integer": "INTEGER",
        "float": "REAL",
        "decimal": "REAL",
        "boolean": "INTEGER",
        "bool": "INTEGER",
        "datetime": "TEXT",
        "date": "TEXT",
        "json": "TEXT",
        "uuid": "TEXT",
    },
}


@dataclass
class SchemaField:
    """Represents a database field."""

    name: str
    type: str
    nullable: bool = True
    unique: bool = False
    default: Optional[str] = None
    foreign_key: Optional[str] = None


@dataclass
class SchemaModel:
    """Represents a database model/table."""

    name: str
    fields: List[SchemaField]
    relations: List[Dict[str, Any]]


async def design_schema(
    context: Dict[str, Any],
    description: str,
    database_type: str = "postgresql",
    orm: Optional[str] = None,
) -> ToolResult:
    """
    Design a database schema from natural language description.

    Parses the description to extract entities, fields, and relationships,
    then generates the appropriate schema definition.

    Args:
        description: Natural language description of the data model
        database_type: Database type (postgresql, mysql, sqlite)
        orm: ORM to use (prisma, drizzle, sqlalchemy, typeorm, django, or None for raw SQL)

    Returns:
        ToolResult with generated schema
    """
    logger.info(
        "design_schema",
        description=description[:100],
        database_type=database_type,
        orm=orm,
    )

    # Parse description to extract models
    models = _parse_schema_description(description)

    if not models:
        return ToolResult(
            output="Could not extract schema from description.\n\n"
            "Try a format like:\n"
            "- 'Users with email, name, and password. Posts with title, content, and author (user).'\n"
            "- 'Products (name, price, description), Categories (name), and OrderItems (product, quantity, price)'",
            sources=[],
        )

    # Generate schema
    if orm and orm in ORM_TEMPLATES:
        schema_code = _generate_orm_schema(models, orm)
        code_type = orm
    else:
        schema_code = _generate_sql_schema(models, database_type)
        code_type = "sql"

    lines = ["## Generated Database Schema\n"]
    lines.append(f"**Database**: {database_type}")
    if orm:
        lines.append(f"**ORM**: {orm}")
    lines.append(f"**Models**: {len(models)}")

    for model in models:
        lines.append(f"- **{model.name}**: {len(model.fields)} fields")

    lines.append("\n**Generated Schema**:")
    lines.append(f"```{code_type}")
    lines.append(schema_code)
    lines.append("```")

    lines.append("\n### Next Steps")
    if orm == "prisma":
        lines.append("1. Add to `prisma/schema.prisma`")
        lines.append("2. Run `npx prisma migrate dev --name init`")
        lines.append("3. Run `npx prisma generate`")
    elif orm == "drizzle":
        lines.append("1. Add to `src/db/schema.ts`")
        lines.append("2. Run `npx drizzle-kit push:pg`")
    elif orm == "sqlalchemy":
        lines.append("1. Add to `app/models/`")
        lines.append("2. Run `alembic revision --autogenerate -m 'Add models'`")
        lines.append("3. Run `alembic upgrade head`")
    elif orm == "django":
        lines.append("1. Add to `app/models.py`")
        lines.append("2. Run `python manage.py makemigrations`")
        lines.append("3. Run `python manage.py migrate`")
    else:
        lines.append("1. Save to a migration file")
        lines.append("2. Execute against your database")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_migration(
    context: Dict[str, Any],
    workspace_path: str,
    changes: List[Dict[str, Any]],
    migration_name: str,
) -> ToolResult:
    """
    Generate a database migration file.

    Args:
        workspace_path: Path to the project root
        changes: List of changes (add_table, add_column, remove_column, etc.)
        migration_name: Name for the migration

    Returns:
        ToolResult with generated migration code
    """
    logger.info(
        "generate_migration",
        workspace_path=workspace_path,
        migration_name=migration_name,
    )

    # Detect ORM from project
    orm = _detect_orm(workspace_path)

    if not orm:
        return ToolResult(
            output="Could not detect ORM/migration tool in project.\n\n"
            "Looking for: Prisma, Drizzle, Alembic, Django, or TypeORM",
            sources=[],
        )

    # Generate migration based on ORM
    if orm == "prisma":
        migration_code = _generate_prisma_migration(changes)
    elif orm == "alembic":
        migration_code = _generate_alembic_migration(changes, migration_name)
    elif orm == "drizzle":
        migration_code = _generate_drizzle_migration(changes)
    elif orm == "django":
        migration_code = _generate_django_migration(changes, migration_name)
    elif orm == "typeorm":
        migration_code = _generate_typeorm_migration(changes, migration_name)
    else:
        migration_code = _generate_sql_migration(changes)

    lines = ["## Generated Migration\n"]
    lines.append(f"**ORM**: {orm}")
    lines.append(f"**Migration Name**: {migration_name}")
    lines.append(f"**Changes**: {len(changes)}")

    for change in changes:
        action = change.get("action", "unknown")
        target = change.get("table", change.get("name", ""))
        lines.append(f"- {action}: {target}")

    lines.append("\n**Migration Code**:")
    lines.append(
        "```python"
        if orm in ("alembic", "django")
        else "```typescript" if orm in ("drizzle", "typeorm") else "```sql"
    )
    lines.append(migration_code)
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def run_migration(
    context: Dict[str, Any],
    workspace_path: str,
    direction: str = "up",
    dry_run: bool = False,
) -> ToolResult:
    """
    Generate command to run database migrations.

    Args:
        workspace_path: Path to the project root
        direction: Migration direction (up, down)
        dry_run: If True, only show what would be done

    Returns:
        ToolResult with migration command
    """
    logger.info("run_migration", workspace_path=workspace_path, direction=direction)

    orm = _detect_orm(workspace_path)

    if not orm:
        return ToolResult(
            output="Could not detect ORM in project.",
            sources=[],
        )

    # Build command based on ORM
    commands = {
        "prisma": {
            "up": "npx prisma migrate deploy",
            "down": "npx prisma migrate reset",
            "dry_run": "npx prisma migrate diff",
        },
        "alembic": {
            "up": "alembic upgrade head",
            "down": "alembic downgrade -1",
            "dry_run": "alembic upgrade head --sql",
        },
        "drizzle": {
            "up": "npx drizzle-kit push:pg",
            "down": "# Drizzle does not support rollback",
            "dry_run": "npx drizzle-kit push:pg --dry-run",
        },
        "django": {
            "up": "python manage.py migrate",
            "down": "python manage.py migrate <app_name> <previous_migration>",
            "dry_run": "python manage.py migrate --plan",
        },
        "typeorm": {
            "up": "npx typeorm migration:run -d src/data-source.ts",
            "down": "npx typeorm migration:revert -d src/data-source.ts",
            "dry_run": "npx typeorm migration:show -d src/data-source.ts",
        },
    }

    orm_commands = commands.get(orm, {})
    cmd_key = "dry_run" if dry_run else direction

    command = orm_commands.get(cmd_key, f"# Unknown command for {orm}")

    lines = ["## Database Migration Command\n"]
    lines.append(f"**ORM**: {orm}")
    lines.append(f"**Direction**: {direction}")
    lines.append(f"**Dry Run**: {dry_run}")

    lines.append("\n**Command**:")
    lines.append("```bash")
    lines.append(command)
    lines.append("```")

    if direction == "up":
        lines.append("\n**Notes**:")
        lines.append("- Ensure your database connection is configured")
        lines.append("- Back up your database before running migrations in production")
        lines.append("- Test migrations in a staging environment first")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_seed_data(
    context: Dict[str, Any],
    workspace_path: str,
    models: List[str],
    count: int = 10,
) -> ToolResult:
    """
    Generate seed data for database models.

    Args:
        workspace_path: Path to the project root
        models: List of model names to seed
        count: Number of records per model

    Returns:
        ToolResult with seed data code
    """
    logger.info("generate_seed_data", workspace_path=workspace_path, models=models)

    orm = _detect_orm(workspace_path)

    seed_code = _generate_seed_code(models, count, orm or "prisma")

    lines = ["## Generated Seed Data\n"]
    lines.append(f"**Models**: {', '.join(models)}")
    lines.append(f"**Records per Model**: {count}")
    lines.append(f"**ORM**: {orm or 'prisma'}")

    lines.append("\n**Seed Code**:")
    lines.append(
        "```typescript" if orm in ("prisma", "drizzle", "typeorm") else "```python"
    )
    lines.append(seed_code)
    lines.append("```")

    lines.append("\n### Running Seeds")
    if orm == "prisma":
        lines.append("```bash")
        lines.append("npx prisma db seed")
        lines.append("```")
    elif orm in ("alembic", "django"):
        lines.append("```bash")
        lines.append("python scripts/seed.py")
        lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def analyze_schema(
    context: Dict[str, Any],
    workspace_path: str,
) -> ToolResult:
    """
    Analyze existing database schema.

    Args:
        workspace_path: Path to the project root

    Returns:
        ToolResult with schema analysis
    """
    logger.info("analyze_schema", workspace_path=workspace_path)

    orm = _detect_orm(workspace_path)
    analysis = {
        "orm": orm,
        "models": [],
        "issues": [],
        "suggestions": [],
    }

    # Find schema files
    schema_files = _find_schema_files(workspace_path, orm)

    if not schema_files:
        return ToolResult(
            output=f"No schema files found for {orm or 'any ORM'}.\n\n"
            f"Looking for: schema.prisma, models.py, schema.ts, or *.entity.ts",
            sources=[],
        )

    for schema_file in schema_files:
        models = _parse_schema_file(schema_file, orm)
        analysis["models"].extend(models)

    # Analyze for common issues
    for model in analysis["models"]:
        # Check for missing timestamps
        field_names = [f["name"].lower() for f in model.get("fields", [])]
        if "createdat" not in field_names and "created_at" not in field_names:
            analysis["issues"].append(
                f"{model['name']}: Missing createdAt/created_at timestamp"
            )

        # Check for missing indexes
        if len(model.get("fields", [])) > 5:
            analysis["suggestions"].append(
                f"{model['name']}: Consider adding indexes for frequently queried fields"
            )

    lines = ["## Schema Analysis\n"]
    lines.append(f"**ORM**: {orm}")
    lines.append(f"**Schema Files**: {len(schema_files)}")
    lines.append(f"**Models Found**: {len(analysis['models'])}")

    if analysis["models"]:
        lines.append("\n### Models")
        for model in analysis["models"]:
            lines.append(
                f"- **{model['name']}**: {len(model.get('fields', []))} fields"
            )

    if analysis["issues"]:
        lines.append("\n### Issues")
        for issue in analysis["issues"]:
            lines.append(f"- {issue}")

    if analysis["suggestions"]:
        lines.append("\n### Suggestions")
        for suggestion in analysis["suggestions"]:
            lines.append(f"- {suggestion}")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_erd(
    context: Dict[str, Any],
    workspace_path: str,
    format: str = "mermaid",
) -> ToolResult:
    """
    Generate Entity Relationship Diagram from schema.

    Args:
        workspace_path: Path to the project root
        format: Output format (mermaid, plantuml, dbml)

    Returns:
        ToolResult with ERD diagram
    """
    logger.info("generate_erd", workspace_path=workspace_path, format=format)

    orm = _detect_orm(workspace_path)
    schema_files = _find_schema_files(workspace_path, orm)

    models = []
    for schema_file in schema_files:
        models.extend(_parse_schema_file(schema_file, orm))

    if not models:
        return ToolResult(
            output="No models found to generate ERD.",
            sources=[],
        )

    # Generate diagram
    if format == "mermaid":
        diagram = _generate_mermaid_erd(models)
        lang = "mermaid"
    elif format == "plantuml":
        diagram = _generate_plantuml_erd(models)
        lang = "plantuml"
    elif format == "dbml":
        diagram = _generate_dbml(models)
        lang = "dbml"
    else:
        diagram = _generate_mermaid_erd(models)
        lang = "mermaid"

    lines = ["## Entity Relationship Diagram\n"]
    lines.append(f"**Format**: {format}")
    lines.append(f"**Models**: {len(models)}")

    lines.append("\n**Diagram**:")
    lines.append(f"```{lang}")
    lines.append(diagram)
    lines.append("```")

    if format == "mermaid":
        lines.append("\n**Rendering**:")
        lines.append("- GitHub/GitLab markdown will render this automatically")
        lines.append("- Use [Mermaid Live Editor](https://mermaid.live/) to preview")

    return ToolResult(output="\n".join(lines), sources=[])


# Helper functions


def _parse_schema_description(description: str) -> List[SchemaModel]:
    """Parse natural language description into schema models."""
    models = []

    # Split by common delimiters
    parts = re.split(r"[.;]|\band\b|\bwith\b", description, flags=re.IGNORECASE)

    current_model = None
    current_fields = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Look for model names (capitalized words)
        model_match = re.match(r"^([A-Z][a-z]+(?:s)?)\s*(?:\(([^)]+)\))?", part)
        if model_match:
            # Save previous model
            if current_model:
                models.append(
                    SchemaModel(
                        name=current_model,
                        fields=current_fields,
                        relations=[],
                    )
                )

            current_model = model_match.group(1)
            if current_model.endswith("s"):
                current_model = current_model[:-1]  # Remove plural

            current_fields = []

            # Extract fields from parentheses
            if model_match.group(2):
                field_str = model_match.group(2)
                for field in re.split(r",\s*", field_str):
                    field = field.strip()
                    if field:
                        field_name, field_type = _parse_field(field)
                        current_fields.append(
                            SchemaField(
                                name=field_name,
                                type=field_type,
                            )
                        )

        # Look for fields mentioned with "with"
        elif current_model:
            for field in re.split(r",\s*", part):
                field = field.strip()
                if field and not field.startswith("and"):
                    field_name, field_type = _parse_field(field)
                    if field_name:
                        current_fields.append(
                            SchemaField(
                                name=field_name,
                                type=field_type,
                            )
                        )

    # Save last model
    if current_model:
        models.append(
            SchemaModel(
                name=current_model,
                fields=current_fields,
                relations=[],
            )
        )

    return models


def _parse_field(field_str: str) -> tuple:
    """Parse a field string into name and type."""
    field_str = field_str.strip().lower()

    # Common field type mappings
    type_keywords = {
        "email": ("email", "string"),
        "password": ("password", "string"),
        "name": ("name", "string"),
        "title": ("title", "string"),
        "content": ("content", "text"),
        "description": ("description", "text"),
        "body": ("body", "text"),
        "price": ("price", "decimal"),
        "amount": ("amount", "decimal"),
        "quantity": ("quantity", "int"),
        "count": ("count", "int"),
        "age": ("age", "int"),
        "active": ("active", "boolean"),
        "enabled": ("enabled", "boolean"),
        "status": ("status", "string"),
        "date": ("date", "datetime"),
        "created": ("createdAt", "datetime"),
        "updated": ("updatedAt", "datetime"),
        "url": ("url", "string"),
        "image": ("imageUrl", "string"),
    }

    # Check for known field patterns
    for keyword, (name, type_val) in type_keywords.items():
        if keyword in field_str:
            return name, type_val

    # Default to string type
    name = re.sub(r"[^a-z0-9]", "", field_str)
    if name:
        return name, "string"

    return None, None


def _detect_orm(workspace_path: str) -> Optional[str]:
    """Detect ORM from project files."""
    # Check for Prisma
    if os.path.exists(os.path.join(workspace_path, "prisma", "schema.prisma")):
        return "prisma"

    # Check for Drizzle
    if os.path.exists(os.path.join(workspace_path, "drizzle.config.ts")):
        return "drizzle"

    # Check for Alembic (SQLAlchemy)
    if os.path.exists(os.path.join(workspace_path, "alembic.ini")):
        return "alembic"

    # Check for Django
    if os.path.exists(os.path.join(workspace_path, "manage.py")):
        return "django"

    # Check for TypeORM
    package_json_path = os.path.join(workspace_path, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "typeorm" in deps:
                    return "typeorm"
                if "drizzle-orm" in deps:
                    return "drizzle"
                if "@prisma/client" in deps:
                    return "prisma"
        except (json.JSONDecodeError, IOError):
            pass

    return None


def _generate_orm_schema(models: List[SchemaModel], orm: str) -> str:
    """Generate ORM-specific schema code."""
    template = ORM_TEMPLATES.get(orm, ORM_TEMPLATES["prisma"])
    output = []

    for model in models:
        # Generate fields
        fields_code = []
        for field in model.fields:
            field_type = template["field_types"].get(
                field.type, template["field_types"]["string"]
            )

            if orm == "prisma":
                nullable = "?" if field.nullable else ""
                fields_code.append(f"  {field.name} {field_type}{nullable}")
            elif orm == "drizzle":
                field_def = field_type.format(field=field.name)
                if not field.nullable:
                    field_def += ".notNull()"
                fields_code.append(f"  {field.name}: {field_def},")
            elif orm == "sqlalchemy":
                nullable_str = (
                    ", nullable=True" if field.nullable else ", nullable=False"
                )
                fields_code.append(f"    {field.name} = {field_type}{nullable_str}")
            elif orm == "django":
                null_blank = ", null=True, blank=True" if field.nullable else ""
                fields_code.append(f"    {field.name} = {field_type}{null_blank}")
            elif orm == "typeorm":
                field_def = field_type.format(field=field.name)
                fields_code.append(f"  {field_def}")

        # Format model
        model_code = template["model"].format(
            name=model.name,
            name_lower=model.name.lower(),
            name_plural=model.name.lower() + "s",
            fields="\n".join(fields_code),
            relations="",
        )
        output.append(model_code)

    return "\n\n".join(output)


def _generate_sql_schema(models: List[SchemaModel], database_type: str) -> str:
    """Generate raw SQL schema."""
    sql_types = SQL_TYPES.get(database_type, SQL_TYPES["postgresql"])
    output = []

    for model in models:
        table_name = model.name.lower() + "s"
        columns = ["  id SERIAL PRIMARY KEY"]

        for field in model.fields:
            col_type = sql_types.get(field.type, "VARCHAR(255)")
            nullable = "" if field.nullable else " NOT NULL"
            columns.append(f"  {field.name} {col_type}{nullable}")

        columns.append("  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        columns.append("  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        create_table = f"CREATE TABLE {table_name} (\n" + ",\n".join(columns) + "\n);"
        output.append(create_table)

    return "\n\n".join(output)


def _find_schema_files(workspace_path: str, orm: Optional[str]) -> List[str]:
    """Find schema definition files."""
    files = []

    if orm == "prisma":
        prisma_schema = os.path.join(workspace_path, "prisma", "schema.prisma")
        if os.path.exists(prisma_schema):
            files.append(prisma_schema)

    elif orm == "alembic":
        models_dir = os.path.join(workspace_path, "app", "models")
        if os.path.exists(models_dir):
            for f in os.listdir(models_dir):
                if f.endswith(".py") and f != "__init___py":
                    files.append(os.path.join(models_dir, f))

    elif orm == "django":
        for root, dirs, filenames in os.walk(workspace_path):
            if "models.py" in filenames:
                files.append(os.path.join(root, "models.py"))

    elif orm in ("drizzle", "typeorm"):
        for root, dirs, filenames in os.walk(workspace_path):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git")]
            for f in filenames:
                if f == "schema.ts" or f.endswith(".entity.ts"):
                    files.append(os.path.join(root, f))

    return files


def _parse_schema_file(file_path: str, orm: Optional[str]) -> List[Dict]:
    """Parse schema file to extract models."""
    models = []

    try:
        with open(file_path, "r") as f:
            content = f.read()

        if orm == "prisma":
            # Parse Prisma schema
            model_pattern = r"model\s+(\w+)\s*\{([^}]+)\}"
            for match in re.finditer(model_pattern, content):
                name = match.group(1)
                body = match.group(2)
                fields = []
                for line in body.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("//") and not line.startswith("@@"):
                        parts = line.split()
                        if len(parts) >= 2:
                            fields.append({"name": parts[0], "type": parts[1]})
                models.append({"name": name, "fields": fields})

        elif orm in ("alembic", "django"):
            # Parse Python class definitions
            class_pattern = r"class\s+(\w+)\s*\([^)]*\):"
            for match in re.finditer(class_pattern, content):
                name = match.group(1)
                if name not in ("Base", "Model"):
                    models.append({"name": name, "fields": []})

    except IOError:
        pass

    return models


def _generate_mermaid_erd(models: List[Dict]) -> str:
    """Generate Mermaid ERD diagram."""
    lines = ["erDiagram"]

    for model in models:
        name = model["name"]
        fields = model.get("fields", [])

        lines.append(f"    {name} {{")
        lines.append("        int id PK")
        for field in fields[:10]:  # Limit fields
            field_name = field.get("name", "unknown")
            field_type = field.get("type", "string").lower()
            lines.append(f"        {field_type} {field_name}")
        lines.append("    }")

    return "\n".join(lines)


def _generate_plantuml_erd(models: List[Dict]) -> str:
    """Generate PlantUML ERD diagram."""
    lines = ["@startuml"]

    for model in models:
        name = model["name"]
        lines.append(f"entity {name} {{")
        lines.append("  *id : int")
        for field in model.get("fields", [])[:10]:
            lines.append(
                f"  {field.get('name', 'unknown')} : {field.get('type', 'string')}"
            )
        lines.append("}")

    lines.append("@enduml")
    return "\n".join(lines)


def _generate_dbml(models: List[Dict]) -> str:
    """Generate DBML schema."""
    lines = []

    for model in models:
        name = model["name"].lower() + "s"
        lines.append(f"Table {name} {{")
        lines.append("  id int [pk, increment]")
        for field in model.get("fields", []):
            lines.append(
                f"  {field.get('name', 'unknown')} {field.get('type', 'varchar')}"
            )
        lines.append("  created_at timestamp [default: `now()`]")
        lines.append("  updated_at timestamp")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def _generate_prisma_migration(changes: List[Dict]) -> str:
    """Generate Prisma migration schema changes."""
    output = ["-- Prisma Migration"]
    for change in changes:
        action = change.get("action")
        if action == "add_table":
            table = change.get("name", "new_table")
            output.append("\n-- CreateTable")
            output.append(f'CREATE TABLE "{table}" (')
            output.append('  "id" SERIAL PRIMARY KEY')
            output.append(");")
        elif action == "add_column":
            table = change.get("table", "table")
            column = change.get("column", "new_column")
            col_type = change.get("type", "VARCHAR(255)")
            output.append(f'\nALTER TABLE "{table}" ADD COLUMN "{column}" {col_type};')
    return "\n".join(output)


def _generate_alembic_migration(changes: List[Dict], name: str) -> str:
    """Generate Alembic migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = [
        f'''"""
{name}

Revision ID: {timestamp}
"""
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:'''
    ]

    for change in changes:
        action = change.get("action")
        if action == "add_table":
            table = change.get("name", "new_table")
            output.append(
                f"""    op.create_table(
        "{table}",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
    )"""
            )
        elif action == "add_column":
            table = change.get("table")
            column = change.get("column")
            output.append(
                f'    op.add_column("{table}", sa.Column("{column}", sa.String(255)))'
            )

    output.append("\n\ndef downgrade() -> None:")
    output.append("    pass")

    return "\n".join(output)


def _generate_drizzle_migration(changes: List[Dict]) -> str:
    """Generate Drizzle migration."""
    return "// Drizzle uses schema push instead of explicit migrations\n// Run: npx drizzle-kit push:pg"


def _generate_django_migration(changes: List[Dict], name: str) -> str:
    """Generate Django migration."""
    output = [
        """from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        # Add dependencies
    ]

    operations = ["""
    ]

    for change in changes:
        action = change.get("action")
        if action == "add_table":
            model = change.get("name", "NewModel")
            output.append(
                f"""        migrations.CreateModel(
            name="{model}",
            fields=[
                ("id", models.AutoField(primary_key=True)),
            ],
        ),"""
            )
        elif action == "add_column":
            model = change.get("table")
            field = change.get("column")
            output.append(
                f"""        migrations.AddField(
            model_name="{model.lower()}",
            name="{field}",
            field=models.CharField(max_length=255, null=True),
        ),"""
            )

    output.append("    ]")
    return "\n".join(output)


def _generate_typeorm_migration(changes: List[Dict], name: str) -> str:
    """Generate TypeORM migration."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    class_name = name.replace("-", "").replace("_", "").title()

    output = [
        f"""import {{ MigrationInterface, QueryRunner, Table }} from "typeorm";

export class {class_name}{timestamp} implements MigrationInterface {{
    public async up(queryRunner: QueryRunner): Promise<void> {{"""
    ]

    for change in changes:
        action = change.get("action")
        if action == "add_table":
            table = change.get("name", "new_table")
            output.append(
                f"""        await queryRunner.createTable(
            new Table({{
                name: "{table}",
                columns: [
                    {{ name: "id", type: "int", isPrimary: true, isGenerated: true }},
                ],
            }}),
            true
        );"""
            )

    output.append(
        """    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        // Rollback
    }
}"""
    )

    return "\n".join(output)


def _generate_sql_migration(changes: List[Dict]) -> str:
    """Generate raw SQL migration."""
    output = ["-- SQL Migration"]
    for change in changes:
        action = change.get("action")
        if action == "add_table":
            table = change.get("name", "new_table")
            output.append(f"\nCREATE TABLE {table} (")
            output.append("  id SERIAL PRIMARY KEY,")
            output.append("  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            output.append(");")
        elif action == "add_column":
            table = change.get("table")
            column = change.get("column")
            col_type = change.get("type", "VARCHAR(255)")
            output.append(f"\nALTER TABLE {table} ADD COLUMN {column} {col_type};")
    return "\n".join(output)


def _generate_seed_code(models: List[str], count: int, orm: str) -> str:
    """Generate seed data code."""
    if orm == "prisma":
        output = [
            """import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {"""
        ]

        for model in models:
            model_lower = model.lower()
            output.append(
                f"""
  // Seed {model}
  for (let i = 0; i < {count}; i++) {{
    await prisma.{model_lower}.create({{
      data: {{
        // Add seed data fields
      }},
    }});
  }}"""
            )

        output.append(
            """
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });"""
        )
        return "\n".join(output)

    elif orm in ("alembic", "django"):
        output = [
            '''"""
Database seed script
"""
from app.database import SessionLocal
# from app.models import Model

def seed():
    db = SessionLocal()
    try:'''
        ]

        for model in models:
            output.append(
                f"""
        # Seed {model}
        for i in range({count}):
            obj = {model}(
                # Add seed data fields
            )
            db.add(obj)"""
            )

        output.append(
            """
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    seed()"""
        )
        return "\n".join(output)

    return "// Seed code not available for this ORM"


# =============================================================================
# REAL EXECUTION FUNCTIONS - Actually run database operations
# =============================================================================


async def execute_migration(
    context: Dict[str, Any],
    workspace_path: str,
    direction: str = "up",
    target: Optional[str] = None,
    dry_run: bool = False,
) -> ToolResult:
    """
    REAL EXECUTION: Actually run database migrations.

    This function executes migrations against your database.
    A confirmation request will be created for user approval.

    Args:
        workspace_path: Path to the project root
        direction: Migration direction ("up" or "down")
        target: Specific migration target (optional)
        dry_run: If True, only show what would be done

    Returns:
        ToolResult with confirmation request or execution result
    """
    logger.info(
        "execute_migration",
        workspace_path=workspace_path,
        direction=direction,
        dry_run=dry_run,
    )

    # Detect migration tool
    migration_info = await database_executor_service.detect_migration_tool(
        workspace_path
    )

    if not migration_info.get("tool"):
        return ToolResult(
            output="❌ No migration tool detected in project.\n\n"
            "Looking for: Prisma, Drizzle, Alembic, Django, Knex, TypeORM, Sequelize, Flyway, Goose\n\n"
            "Make sure you have a migration tool configured.",
            sources=[],
        )

    tool_name = migration_info["tool"]

    # Determine risk level based on direction and environment
    if direction == "down":
        risk_level = RiskLevel.HIGH
        risk_description = "Rolling back migrations may cause data loss"
    elif dry_run:
        risk_level = RiskLevel.LOW
        risk_description = "Dry run - no actual changes will be made"
    else:
        risk_level = RiskLevel.MEDIUM
        risk_description = "Applying migrations will modify database schema"

    # Create execution request for confirmation
    request = await execution_confirmation_service.create_execution_request(
        operation="db.execute_migration",
        category=OperationCategory.DATABASE,
        parameters={
            "workspace_path": workspace_path,
            "direction": direction,
            "tool": tool_name,
            "target": target,
            "dry_run": dry_run,
        },
        risk_level=risk_level,
        description=f"Execute database migration ({direction}) using {tool_name}",
        affected_resources=[
            f"Migration tool: {tool_name}",
            f"Direction: {direction}",
            f"Workspace: {workspace_path}",
        ],
        warnings=[
            {
                "level": risk_level.value,
                "title": "Database Schema Change",
                "message": risk_description,
                "details": [
                    f"Tool: {tool_name}",
                    f"Direction: {direction}",
                    f"Target: {target or 'latest'}",
                ],
                "mitigation": "Ensure you have a database backup before proceeding",
                "rollback_available": direction == "up",
                "rollback_instructions": (
                    "Run migration down: db.execute_migration with direction='down'"
                    if direction == "up"
                    else None
                ),
            }
        ],
        rollback_plan=(
            f"Run migration in opposite direction ({('down' if direction == 'up' else 'up')})"
            if not dry_run
            else None
        ),
    )

    lines = ["## Database Migration Request Created\n"]
    lines.append(f"**Request ID**: `{request.id}`")
    lines.append(f"**Operation**: Execute migration ({direction})")
    lines.append(f"**Tool**: {tool_name}")
    lines.append(f"**Risk Level**: {request.risk_level.value.upper()}")
    lines.append(f"**Dry Run**: {dry_run}")
    lines.append("\n**⚠️ Requires Confirmation**")
    lines.append("This operation will modify your database schema.")
    lines.append(f"\nCall `db.confirm` with request_id='{request.id}' to execute.")

    if request.confirmation_phrase:
        lines.append(f"\n**Confirmation Phrase**: `{request.confirmation_phrase}`")

    return ToolResult(
        output="\n".join(lines),
        sources=[],
        metadata={
            "execution_request": {
                "id": request.id,
                "risk_level": request.risk_level.value,
                "requires_confirmation": request.requires_confirmation,
                "confirmation_phrase": request.confirmation_phrase,
                "ui_config": request.ui_config,
            }
        },
    )


async def confirm_database_operation(
    context: Dict[str, Any],
    request_id: str,
    confirmation_input: Optional[str] = None,
) -> ToolResult:
    """
    Confirm and execute a pending database operation.

    Args:
        request_id: The execution request ID to confirm
        confirmation_input: Confirmation phrase if required

    Returns:
        ToolResult with execution result
    """
    logger.info("confirm_database_operation", request_id=request_id)

    # Validate the request
    request = execution_confirmation_service.get_pending_request(request_id)

    if not request:
        return ToolResult(
            output=f"❌ No pending request found with ID: {request_id}\n\n"
            "The request may have expired or already been processed.",
            sources=[],
        )

    # Verify confirmation phrase if required
    if request.confirmation_phrase:
        if not confirmation_input:
            return ToolResult(
                output=f"❌ Confirmation phrase required.\n\n"
                f"Please provide the phrase: `{request.confirmation_phrase}`",
                sources=[],
            )
        if confirmation_input.upper() != request.confirmation_phrase.upper():
            return ToolResult(
                output=f"❌ Invalid confirmation phrase.\n\n"
                f"Expected: `{request.confirmation_phrase}`\n"
                f"Received: `{confirmation_input}`",
                sources=[],
            )

    # Mark as approved
    await execution_confirmation_service.approve_request(request_id, confirmation_input)

    # Execute the operation
    params = request.parameters
    workspace_path = params.get("workspace_path")
    direction = params.get("direction", "up")
    target = params.get("target")
    dry_run = params.get("dry_run", False)

    migration_dir = (
        MigrationDirection.UP if direction == "up" else MigrationDirection.DOWN
    )

    # Run the migration
    result = await database_executor_service.run_migration(
        workspace_path=workspace_path,
        direction=migration_dir,
        target=target,
        dry_run=dry_run,
    )

    lines = ["## Database Migration Executed\n"]

    if result.success:
        lines.append("✅ **Migration completed successfully!**\n")
        lines.append(f"**Tool**: {result.tool}")
        lines.append(f"**Direction**: {direction}")

        if result.migrations_applied:
            lines.append("\n**Migrations Applied**:")
            for migration in result.migrations_applied:
                lines.append(f"- {migration}")

        if result.output:
            lines.append("\n**Output**:")
            lines.append("```")
            lines.append(result.output[:2000])  # Limit output
            lines.append("```")
    else:
        lines.append("❌ **Migration failed**\n")
        lines.append(f"**Error**: {result.error}")

        if result.output:
            lines.append("\n**Output**:")
            lines.append("```")
            lines.append(result.output[:2000])
            lines.append("```")

        if result.rollback_command:
            lines.append("\n**Rollback Command**:")
            lines.append("```bash")
            lines.append(result.rollback_command)
            lines.append("```")

    return ToolResult(
        output="\n".join(lines),
        sources=[],
        metadata={
            "execution_result": {
                "success": result.success,
                "tool": result.tool,
                "migrations_applied": result.migrations_applied,
                "error": result.error,
            }
        },
    )


async def backup_database(
    context: Dict[str, Any],
    workspace_path: str,
    database_url: Optional[str] = None,
    output_path: Optional[str] = None,
    compression: bool = True,
) -> ToolResult:
    """
    REAL EXECUTION: Create a database backup.

    Args:
        workspace_path: Path to the project root
        database_url: Database connection URL (or read from env)
        output_path: Where to save the backup
        compression: Whether to compress the backup

    Returns:
        ToolResult with backup result
    """
    logger.info("backup_database", workspace_path=workspace_path)

    # Create execution request for confirmation
    request = await execution_confirmation_service.create_execution_request(
        operation="db.backup",
        category=OperationCategory.DATABASE,
        parameters={
            "workspace_path": workspace_path,
            "database_url": database_url,
            "output_path": output_path,
            "compression": compression,
        },
        risk_level=RiskLevel.LOW,
        description="Create database backup",
        affected_resources=[
            f"Workspace: {workspace_path}",
            f"Output: {output_path or 'auto-generated'}",
        ],
        warnings=[
            {
                "level": "low",
                "title": "Database Backup",
                "message": "This will create a backup of your database",
                "details": [
                    "Backup will be saved locally",
                    f"Compression: {'enabled' if compression else 'disabled'}",
                ],
                "mitigation": "Ensure sufficient disk space is available",
            }
        ],
    )

    lines = ["## Database Backup Request Created\n"]
    lines.append(f"**Request ID**: `{request.id}`")
    lines.append("**Risk Level**: LOW")
    lines.append(f"**Compression**: {compression}")
    lines.append(
        f"\nCall `db.confirm` with request_id='{request.id}' to execute backup."
    )

    return ToolResult(
        output="\n".join(lines),
        sources=[],
        metadata={
            "execution_request": {
                "id": request.id,
                "risk_level": request.risk_level.value,
            }
        },
    )


async def restore_database(
    context: Dict[str, Any],
    workspace_path: str,
    backup_path: str,
    database_url: Optional[str] = None,
) -> ToolResult:
    """
    REAL EXECUTION: Restore database from backup.

    This is a CRITICAL operation that will overwrite the current database.

    Args:
        workspace_path: Path to the project root
        backup_path: Path to the backup file
        database_url: Database connection URL (or read from env)

    Returns:
        ToolResult with confirmation request
    """
    logger.info(
        "restore_database", workspace_path=workspace_path, backup_path=backup_path
    )

    # Verify backup file exists
    if not os.path.exists(backup_path):
        return ToolResult(
            output=f"❌ Backup file not found: {backup_path}",
            sources=[],
        )

    # Create execution request for confirmation
    request = await execution_confirmation_service.create_execution_request(
        operation="db.restore",
        category=OperationCategory.DATABASE,
        parameters={
            "workspace_path": workspace_path,
            "backup_path": backup_path,
            "database_url": database_url,
        },
        risk_level=RiskLevel.CRITICAL,
        description="Restore database from backup - THIS WILL OVERWRITE ALL CURRENT DATA",
        affected_resources=[
            f"Backup file: {backup_path}",
            f"Workspace: {workspace_path}",
            "ALL current database data will be replaced",
        ],
        warnings=[
            {
                "level": "critical",
                "title": "Database Restore - Data Overwrite",
                "message": "This operation will COMPLETELY REPLACE your current database with the backup",
                "details": [
                    "All current data will be lost",
                    "This cannot be undone without another backup",
                    f"Backup source: {backup_path}",
                ],
                "mitigation": "Create a backup of current database before restoring",
                "rollback_available": False,
            }
        ],
        rollback_plan="Not available - create a backup before restore",
    )

    lines = ["## 🚨 CRITICAL: Database Restore Request\n"]
    lines.append(f"**Request ID**: `{request.id}`")
    lines.append("**Risk Level**: CRITICAL")
    lines.append(f"**Backup File**: {backup_path}")
    lines.append("\n**⚠️ WARNING**: This will overwrite ALL current database data!")
    lines.append("\n**Confirmation Required**")
    lines.append(f"Type the phrase: `{request.confirmation_phrase}`")
    lines.append(
        f"\nCall `db.confirm` with request_id='{request.id}' and confirmation_input='{request.confirmation_phrase}'"
    )

    return ToolResult(
        output="\n".join(lines),
        sources=[],
        metadata={
            "execution_request": {
                "id": request.id,
                "risk_level": request.risk_level.value,
                "requires_confirmation": True,
                "confirmation_phrase": request.confirmation_phrase,
                "ui_config": request.ui_config,
            }
        },
    )


async def get_migration_status(
    context: Dict[str, Any],
    workspace_path: str,
) -> ToolResult:
    """
    Get the current migration status of the database.

    Args:
        workspace_path: Path to the project root

    Returns:
        ToolResult with migration status
    """
    logger.info("get_migration_status", workspace_path=workspace_path)

    # Detect migration tool
    migration_info = await database_executor_service.detect_migration_tool(
        workspace_path
    )

    if not migration_info.get("tool"):
        return ToolResult(
            output="❌ No migration tool detected in project.",
            sources=[],
        )

    tool_name = migration_info["tool"]

    # Get status based on tool
    status_commands = {
        "prisma": "npx prisma migrate status",
        "alembic": "alembic current",
        "django": "python manage.py showmigrations",
        "knex": "npx knex migrate:status",
        "typeorm": "npx typeorm migration:show -d src/data-source.ts",
        "sequelize": "npx sequelize-cli db:migrate:status",
        "drizzle": "npx drizzle-kit check:pg",
        "flyway": "flyway info",
        "goose": "goose status",
    }

    cmd = status_commands.get(tool_name, "# Unknown tool")

    lines = ["## Migration Status\n"]
    lines.append(f"**Tool**: {tool_name}")
    lines.append(f"**Workspace**: {workspace_path}")
    lines.append("\n**Check Status Command**:")
    lines.append("```bash")
    lines.append(f"cd {workspace_path}")
    lines.append(cmd)
    lines.append("```")

    if migration_info.get("config_file"):
        lines.append(f"\n**Config File**: {migration_info['config_file']}")

    if migration_info.get("migrations_dir"):
        lines.append(f"**Migrations Directory**: {migration_info['migrations_dir']}")

    return ToolResult(
        output="\n".join(lines),
        sources=[],
    )


# Export tools for the agent dispatcher
DATABASE_TOOLS = {
    # Schema design tools (generation only)
    "db_design_schema": design_schema,
    "db_generate_migration": generate_migration,
    "db_run_migration": run_migration,  # Shows command only
    "db_generate_seed": generate_seed_data,
    "db_analyze_schema": analyze_schema,
    "db_generate_erd": generate_erd,
    # Real execution tools
    "db_execute_migration": execute_migration,
    "db_confirm": confirm_database_operation,
    "db_backup": backup_database,
    "db_restore": restore_database,
    "db_status": get_migration_status,
}
