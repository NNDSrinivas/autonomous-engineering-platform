"""
Advanced Database Tools for Enterprise NAVI.

Provides tools for enterprise database operations:
- Migration orchestration across environments
- Replication setup and monitoring
- Sharding configuration
- Backup and restore operations
- Query performance analysis

Supports PostgreSQL, MySQL, MongoDB, and Redis.
"""

import os
import subprocess
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MigrationStep:
    """A database migration step."""

    version: str
    name: str
    up_sql: str
    down_sql: str
    checksum: Optional[str] = None


async def db_orchestrate_migration(
    user_id: str,
    workspace_path: str,
    migration_tool: str = "auto",
    target_env: str = "development",
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Orchestrate database migrations across environments.

    Detects migration tool (Alembic, Prisma, Flyway, etc.) and runs migrations.

    Args:
        user_id: User ID executing the tool
        workspace_path: Path to the project
        migration_tool: Tool to use (auto, alembic, prisma, flyway, knex, typeorm)
        target_env: Target environment (development, staging, production)
        dry_run: If True, show what would be done without executing

    Returns:
        Migration execution result
    """
    logger.info(
        "[TOOL:db_orchestrate_migration] Orchestrating migrations",
        workspace=workspace_path,
        tool=migration_tool,
        env=target_env,
    )

    # Auto-detect migration tool
    detected_tool = None
    migration_files = []

    if migration_tool == "auto":
        # Check for Alembic (Python/SQLAlchemy)
        if os.path.exists(os.path.join(workspace_path, "alembic.ini")):
            detected_tool = "alembic"
            alembic_dir = os.path.join(workspace_path, "alembic", "versions")
            if os.path.exists(alembic_dir):
                migration_files = os.listdir(alembic_dir)

        # Check for Prisma (Node.js)
        elif os.path.exists(os.path.join(workspace_path, "prisma", "schema.prisma")):
            detected_tool = "prisma"
            migrations_dir = os.path.join(workspace_path, "prisma", "migrations")
            if os.path.exists(migrations_dir):
                migration_files = os.listdir(migrations_dir)

        # Check for Flyway (Java)
        elif os.path.exists(os.path.join(workspace_path, "flyway.conf")):
            detected_tool = "flyway"

        # Check for Knex (Node.js)
        elif os.path.exists(os.path.join(workspace_path, "knexfile.js")):
            detected_tool = "knex"

        # Check for TypeORM
        elif os.path.exists(os.path.join(workspace_path, "ormconfig.json")):
            detected_tool = "typeorm"

        # Check for Django
        elif os.path.exists(os.path.join(workspace_path, "manage.py")):
            detected_tool = "django"
    else:
        detected_tool = migration_tool

    if not detected_tool:
        return {
            "success": False,
            "error": "Could not detect migration tool. Please specify one.",
            "supported_tools": [
                "alembic",
                "prisma",
                "flyway",
                "knex",
                "typeorm",
                "django",
            ],
        }

    # Build migration command
    commands = {
        "alembic": {
            "status": "alembic current",
            "migrate": "alembic upgrade head",
            "rollback": "alembic downgrade -1",
        },
        "prisma": {
            "status": "npx prisma migrate status",
            "migrate": "npx prisma migrate deploy",
            "rollback": "npx prisma migrate reset --force",
        },
        "flyway": {
            "status": "flyway info",
            "migrate": "flyway migrate",
            "rollback": "flyway undo",
        },
        "knex": {
            "status": "npx knex migrate:status",
            "migrate": "npx knex migrate:latest",
            "rollback": "npx knex migrate:rollback",
        },
        "typeorm": {
            "status": "npx typeorm migration:show",
            "migrate": "npx typeorm migration:run",
            "rollback": "npx typeorm migration:revert",
        },
        "django": {
            "status": "python manage.py showmigrations",
            "migrate": "python manage.py migrate",
            "rollback": "python manage.py migrate <app> <previous_migration>",
        },
    }

    tool_commands = commands.get(detected_tool, {})

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "detected_tool": detected_tool,
            "target_env": target_env,
            "migration_files": migration_files[:20],
            "commands": tool_commands,
            "message": f"DRY RUN: Would run {detected_tool} migrations for {target_env}",
            "next_steps": [
                f"1. Verify DATABASE_URL is set for {target_env}",
                f"2. Run status command: {tool_commands.get('status', 'N/A')}",
                f"3. Run migration: {tool_commands.get('migrate', 'N/A')}",
            ],
        }

    # Execute migration (only in development by default)
    if target_env == "production" and not os.environ.get("ALLOW_PROD_MIGRATIONS"):
        return {
            "success": False,
            "error": "Production migrations require ALLOW_PROD_MIGRATIONS=true",
            "detected_tool": detected_tool,
        }

    try:
        # Run status first
        status_result = subprocess.run(
            tool_commands["status"],
            shell=True,
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Run migration
        migrate_result = subprocess.run(
            tool_commands["migrate"],
            shell=True,
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=300,
        )

        return {
            "success": migrate_result.returncode == 0,
            "detected_tool": detected_tool,
            "target_env": target_env,
            "status_output": status_result.stdout[-2000:],
            "migration_output": migrate_result.stdout[-2000:],
            "migration_errors": (
                migrate_result.stderr[-1000:] if migrate_result.stderr else None
            ),
            "message": f"Migration {'completed' if migrate_result.returncode == 0 else 'failed'} using {detected_tool}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "detected_tool": detected_tool,
        }


async def db_setup_replication(
    user_id: str,
    database_type: str,
    primary_host: str,
    replica_host: str,
    database_name: str,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Generate configuration for database replication setup.

    Args:
        user_id: User ID executing the tool
        database_type: Database type (postgres, mysql, mongodb)
        primary_host: Primary database host
        replica_host: Replica database host
        database_name: Database name
        dry_run: If True, generate config without executing

    Returns:
        Replication configuration and setup steps
    """
    logger.info(
        "[TOOL:db_setup_replication] Setting up replication",
        db_type=database_type,
        primary=primary_host,
    )

    configs = {
        "postgres": {
            "primary_config": f"""
# PostgreSQL Primary Configuration (postgresql.conf)
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
synchronous_commit = on
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/archive/%f'

# pg_hba.conf entry for replica
host replication replicator {replica_host}/32 md5
""",
            "replica_config": f"""
# PostgreSQL Replica Configuration
primary_conninfo = 'host={primary_host} port=5432 user=replicator password=your_password application_name=replica1'
restore_command = 'cp /var/lib/postgresql/archive/%f %p'
standby_mode = on
trigger_file = '/tmp/postgresql.trigger'
""",
            "setup_commands": [
                "# On primary: Create replication user",
                "CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'secure_password';",
                "",
                "# On replica: Stop PostgreSQL and backup",
                "sudo systemctl stop postgresql",
                "sudo rm -rf /var/lib/postgresql/data/*",
                "",
                "# On replica: Copy data from primary",
                f"pg_basebackup -h {primary_host} -D /var/lib/postgresql/data -U replicator -v -P --wal-method=stream",
                "",
                "# On replica: Start PostgreSQL",
                "sudo systemctl start postgresql",
            ],
        },
        "mysql": {
            "primary_config": f"""
# MySQL Primary Configuration (my.cnf)
[mysqld]
server-id = 1
log_bin = mysql-bin
binlog_format = ROW
binlog_do_db = {database_name}
gtid_mode = ON
enforce_gtid_consistency = ON
""",
            "replica_config": """
# MySQL Replica Configuration (my.cnf)
[mysqld]
server-id = 2
relay_log = relay-log
log_bin = mysql-bin
read_only = ON
gtid_mode = ON
enforce_gtid_consistency = ON
""",
            "setup_commands": [
                "# On primary: Create replication user",
                f"CREATE USER 'replicator'@'{replica_host}' IDENTIFIED BY 'secure_password';",
                f"GRANT REPLICATION SLAVE ON *.* TO 'replicator'@'{replica_host}';",
                "FLUSH PRIVILEGES;",
                "",
                "# On replica: Configure replication",
                "CHANGE MASTER TO",
                f"  MASTER_HOST='{primary_host}',",
                "  MASTER_USER='replicator',",
                "  MASTER_PASSWORD='secure_password',",
                "  MASTER_AUTO_POSITION=1;",
                "START SLAVE;",
            ],
        },
        "mongodb": {
            "primary_config": """
# MongoDB Replica Set Configuration
# Add to mongod.conf on all nodes
replication:
  replSetName: "rs0"
net:
  bindIp: 0.0.0.0
  port: 27017
security:
  keyFile: /etc/mongodb/keyfile
""",
            "replica_config": "# Same configuration as primary",
            "setup_commands": [
                "# Generate keyfile (same on all nodes)",
                "openssl rand -base64 756 > /etc/mongodb/keyfile",
                "chmod 400 /etc/mongodb/keyfile",
                "chown mongodb:mongodb /etc/mongodb/keyfile",
                "",
                "# On primary: Initialize replica set",
                "mongosh --eval 'rs.initiate({",
                '  _id: "rs0",',
                "  members: [",
                f'    {{ _id: 0, host: "{primary_host}:27017", priority: 2 }},',
                f'    {{ _id: 1, host: "{replica_host}:27017", priority: 1 }}',
                "  ]",
                "})'",
            ],
        },
    }

    if database_type not in configs:
        return {
            "success": False,
            "error": f"Unsupported database type: {database_type}",
            "supported_types": list(configs.keys()),
        }

    config = configs[database_type]

    return {
        "success": True,
        "dry_run": dry_run,
        "database_type": database_type,
        "primary_host": primary_host,
        "replica_host": replica_host,
        "primary_config": config["primary_config"],
        "replica_config": config["replica_config"],
        "setup_commands": config["setup_commands"],
        "monitoring_queries": {
            "postgres": "SELECT * FROM pg_stat_replication;",
            "mysql": "SHOW SLAVE STATUS\\G",
            "mongodb": "rs.status()",
        }.get(database_type),
        "message": f"Replication configuration generated for {database_type}",
        "warnings": [
            "Always test in a staging environment first",
            "Ensure network connectivity between primary and replica",
            "Use strong passwords and secure connections",
            "Set up monitoring for replication lag",
        ],
    }


async def db_configure_sharding(
    user_id: str,
    database_type: str,
    shard_key: str,
    collection_name: str,
    num_shards: int = 3,
) -> Dict[str, Any]:
    """
    Generate sharding configuration for horizontal scaling.

    Args:
        user_id: User ID executing the tool
        database_type: Database type (mongodb, postgres_citus, vitess)
        shard_key: Field to use for sharding
        collection_name: Collection/table to shard
        num_shards: Number of shards

    Returns:
        Sharding configuration and setup steps
    """
    logger.info(
        "[TOOL:db_configure_sharding] Configuring sharding",
        db_type=database_type,
        shard_key=shard_key,
    )

    configs = {
        "mongodb": {
            "config": f"""
// MongoDB Sharding Configuration
// 1. Start config servers (replica set)
// 2. Start shard servers
// 3. Start mongos routers

// Enable sharding on database
sh.enableSharding("{collection_name.split('.')[0] if '.' in collection_name else 'mydb'}")

// Shard collection with hashed key for even distribution
sh.shardCollection("{collection_name}", {{ "{shard_key}": "hashed" }})

// Or use ranged sharding for ordered access patterns
// sh.shardCollection("{collection_name}", {{ "{shard_key}": 1 }})
""",
            "architecture": """
MongoDB Sharding Architecture:
┌─────────────────┐
│   Application   │
└────────┬────────┘
         │
┌────────▼────────┐
│  mongos Router  │
└────────┬────────┘
         │
┌────────▼────────┐
│ Config Servers  │
│   (Replica Set) │
└────────┬────────┘
         │
┌────────┼────────┬────────┐
▼        ▼        ▼        ▼
Shard 1  Shard 2  Shard 3  ...
(RS)     (RS)     (RS)
""",
            "commands": [
                "# Start config server replica set",
                "mongod --configsvr --replSet configReplSet --port 27019",
                "",
                "# Start shard servers",
                "mongod --shardsvr --replSet shard1 --port 27018",
                "mongod --shardsvr --replSet shard2 --port 27020",
                "",
                "# Start mongos router",
                "mongos --configdb configReplSet/localhost:27019",
                "",
                "# Add shards to cluster",
                "sh.addShard('shard1/localhost:27018')",
                "sh.addShard('shard2/localhost:27020')",
            ],
        },
        "postgres_citus": {
            "config": f"""
-- Citus (PostgreSQL) Sharding Configuration

-- Enable Citus extension
CREATE EXTENSION citus;

-- Set coordinator node
SELECT citus_set_coordinator_host('coordinator', 5432);

-- Add worker nodes
SELECT citus_add_node('worker1', 5432);
SELECT citus_add_node('worker2', 5432);

-- Create distributed table
SELECT create_distributed_table('{collection_name}', '{shard_key}');

-- Or create reference table (replicated to all nodes)
-- SELECT create_reference_table('lookup_table');
""",
            "architecture": """
Citus Sharding Architecture:
┌─────────────────┐
│   Application   │
└────────┬────────┘
         │
┌────────▼────────┐
│   Coordinator   │
│   (PostgreSQL)  │
└────────┬────────┘
         │
┌────────┼────────┬────────┐
▼        ▼        ▼        ▼
Worker1  Worker2  Worker3  ...
""",
            "commands": [
                "# Install Citus extension",
                "CREATE EXTENSION citus;",
                "",
                "# Configure coordinator and workers",
                "SELECT citus_add_node('worker1', 5432);",
                "",
                "# Create distributed table",
                f"SELECT create_distributed_table('{collection_name}', '{shard_key}');",
            ],
        },
    }

    if database_type not in configs:
        return {
            "success": False,
            "error": f"Unsupported database type for sharding: {database_type}",
            "supported_types": list(configs.keys()),
        }

    config = configs[database_type]

    return {
        "success": True,
        "database_type": database_type,
        "shard_key": shard_key,
        "collection_name": collection_name,
        "num_shards": num_shards,
        "config": config["config"],
        "architecture": config["architecture"],
        "setup_commands": config["commands"],
        "shard_key_recommendations": [
            "Use high-cardinality field (many unique values)",
            "Avoid monotonically increasing values unless hashed",
            "Consider query patterns - shard key should be in most queries",
            "Avoid using fields that change frequently",
        ],
        "message": f"Sharding configuration generated for {collection_name} using {shard_key}",
    }


async def db_backup_restore(
    user_id: str,
    operation: str,
    database_type: str,
    database_url: str,
    backup_path: Optional[str] = None,
    compression: bool = True,
) -> Dict[str, Any]:
    """
    Generate database backup/restore commands.

    Args:
        user_id: User ID executing the tool
        operation: Operation type (backup, restore, list)
        database_type: Database type (postgres, mysql, mongodb)
        database_url: Database connection URL
        backup_path: Path for backup file
        compression: Whether to compress backup

    Returns:
        Backup/restore commands and status
    """
    logger.info(
        f"[TOOL:db_backup_restore] {operation} operation", db_type=database_type
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_path or f"backup_{database_type}_{timestamp}"

    commands = {
        "postgres": {
            "backup": f"pg_dump {database_url} {'| gzip' if compression else ''} > {backup_path}.{'sql.gz' if compression else 'sql'}",
            "backup_custom": f"pg_dump -Fc {database_url} > {backup_path}.dump",
            "restore": f"{'gunzip -c' if compression else 'cat'} {backup_path} | psql {database_url}",
            "restore_custom": f"pg_restore -d {database_url} {backup_path}",
            "list": "pg_restore --list {backup_path}",
        },
        "mysql": {
            "backup": f"mysqldump --single-transaction {database_url} {'| gzip' if compression else ''} > {backup_path}.{'sql.gz' if compression else 'sql'}",
            "restore": f"{'gunzip -c' if compression else 'cat'} {backup_path} | mysql {database_url}",
        },
        "mongodb": {
            "backup": f"mongodump --uri={database_url} --out={backup_path} {'--gzip' if compression else ''}",
            "restore": f"mongorestore --uri={database_url} {'--gzip' if compression else ''} {backup_path}",
        },
    }

    if database_type not in commands:
        return {
            "success": False,
            "error": f"Unsupported database type: {database_type}",
            "supported_types": list(commands.keys()),
        }

    db_commands = commands[database_type]

    return {
        "success": True,
        "operation": operation,
        "database_type": database_type,
        "backup_path": backup_path,
        "compression": compression,
        "commands": {
            "backup": db_commands.get("backup", "Not available"),
            "restore": db_commands.get("restore", "Not available"),
        },
        "best_practices": [
            "Test restore process regularly",
            "Store backups in multiple locations (e.g., S3 + local)",
            "Encrypt sensitive backups",
            "Set up automated backup schedules",
            "Monitor backup sizes for anomalies",
        ],
        "automation_cron": f"0 2 * * * {db_commands.get('backup', '')}  # Daily at 2 AM",
        "message": f"Backup commands generated for {database_type}",
    }


async def db_analyze_query_performance(
    user_id: str,
    database_type: str,
    database_url: str,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze query performance and provide optimization recommendations.

    Args:
        user_id: User ID executing the tool
        database_type: Database type (postgres, mysql)
        database_url: Database connection URL
        query: Specific query to analyze (optional)

    Returns:
        Performance analysis and recommendations
    """
    logger.info(
        "[TOOL:db_analyze_query_performance] Analyzing performance",
        db_type=database_type,
    )

    analysis_queries = {
        "postgres": {
            "slow_queries": """
SELECT
    query,
    calls,
    mean_exec_time,
    total_exec_time,
    rows
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
""",
            "index_usage": """
SELECT
    schemaname,
    relname as table_name,
    indexrelname as index_name,
    idx_scan as times_used,
    idx_tup_read as tuples_read
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC
LIMIT 10;
""",
            "table_stats": """
SELECT
    schemaname,
    relname as table_name,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes,
    n_live_tup as live_tuples,
    n_dead_tup as dead_tuples
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 10;
""",
            "explain_query": (
                f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}" if query else None
            ),
        },
        "mysql": {
            "slow_queries": """
SELECT
    query,
    exec_count,
    avg_latency,
    rows_examined_avg
FROM sys.statements_with_runtimes_in_95th_percentile
LIMIT 10;
""",
            "index_usage": """
SELECT
    table_schema,
    table_name,
    index_name,
    rows_read
FROM sys.schema_index_statistics
ORDER BY rows_read ASC
LIMIT 10;
""",
            "explain_query": f"EXPLAIN FORMAT=JSON {query}" if query else None,
        },
    }

    if database_type not in analysis_queries:
        return {
            "success": False,
            "error": f"Unsupported database type: {database_type}",
        }

    queries = analysis_queries[database_type]

    return {
        "success": True,
        "database_type": database_type,
        "analysis_queries": queries,
        "optimization_tips": [
            "Add indexes on frequently queried columns",
            "Avoid SELECT * - specify needed columns",
            "Use LIMIT for large result sets",
            "Consider query caching for repeated queries",
            "Normalize or denormalize based on access patterns",
            "Use connection pooling (PgBouncer, ProxySQL)",
            "Regular VACUUM/ANALYZE in PostgreSQL",
            "Monitor slow query logs",
        ],
        "common_issues": {
            "missing_index": "Add index on columns used in WHERE/JOIN",
            "n_plus_one": "Use JOINs or batch queries instead",
            "full_table_scan": "Add appropriate indexes",
            "lock_contention": "Optimize transactions, use row-level locks",
        },
        "message": f"Performance analysis queries generated for {database_type}",
    }


# Tool definitions for NAVI agent
ADVANCED_DATABASE_TOOLS = {
    "db_orchestrate_migration": {
        "function": db_orchestrate_migration,
        "description": "Orchestrate database migrations across environments (Alembic, Prisma, Flyway, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_path": {"type": "string", "description": "Path to project"},
                "migration_tool": {
                    "type": "string",
                    "description": "Tool to use (auto, alembic, prisma, flyway)",
                },
                "target_env": {"type": "string", "description": "Target environment"},
                "dry_run": {
                    "type": "boolean",
                    "description": "Show what would be done without executing",
                },
            },
            "required": ["workspace_path"],
        },
    },
    "db_setup_replication": {
        "function": db_setup_replication,
        "description": "Generate database replication configuration (PostgreSQL, MySQL, MongoDB)",
        "parameters": {
            "type": "object",
            "properties": {
                "database_type": {
                    "type": "string",
                    "enum": ["postgres", "mysql", "mongodb"],
                },
                "primary_host": {
                    "type": "string",
                    "description": "Primary database host",
                },
                "replica_host": {
                    "type": "string",
                    "description": "Replica database host",
                },
                "database_name": {"type": "string", "description": "Database name"},
                "dry_run": {
                    "type": "boolean",
                    "description": "Generate config without executing",
                },
            },
            "required": [
                "database_type",
                "primary_host",
                "replica_host",
                "database_name",
            ],
        },
    },
    "db_configure_sharding": {
        "function": db_configure_sharding,
        "description": "Generate sharding configuration for horizontal scaling",
        "parameters": {
            "type": "object",
            "properties": {
                "database_type": {
                    "type": "string",
                    "enum": ["mongodb", "postgres_citus"],
                },
                "shard_key": {"type": "string", "description": "Field to shard on"},
                "collection_name": {
                    "type": "string",
                    "description": "Collection/table to shard",
                },
                "num_shards": {"type": "integer", "description": "Number of shards"},
            },
            "required": ["database_type", "shard_key", "collection_name"],
        },
    },
    "db_backup_restore": {
        "function": db_backup_restore,
        "description": "Generate backup/restore commands for databases",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["backup", "restore", "list"]},
                "database_type": {
                    "type": "string",
                    "enum": ["postgres", "mysql", "mongodb"],
                },
                "database_url": {
                    "type": "string",
                    "description": "Database connection URL",
                },
                "backup_path": {
                    "type": "string",
                    "description": "Path for backup file",
                },
                "compression": {"type": "boolean", "description": "Compress backup"},
            },
            "required": ["operation", "database_type", "database_url"],
        },
    },
    "db_analyze_query_performance": {
        "function": db_analyze_query_performance,
        "description": "Analyze query performance and get optimization recommendations",
        "parameters": {
            "type": "object",
            "properties": {
                "database_type": {"type": "string", "enum": ["postgres", "mysql"]},
                "database_url": {
                    "type": "string",
                    "description": "Database connection URL",
                },
                "query": {"type": "string", "description": "Specific query to analyze"},
            },
            "required": ["database_type", "database_url"],
        },
    },
}
