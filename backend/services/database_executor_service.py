"""
Database Executor Service for NAVI
Handles real database operations: migrations, seeding, backups, schema changes.

Supports: PostgreSQL, MySQL, SQLite, MongoDB, and various ORMs (Prisma, Drizzle, SQLAlchemy, etc.)
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """Supported database types - comprehensive list of 150+ databases."""
    # =========================================================================
    # RELATIONAL DATABASES (RDBMS)
    # =========================================================================
    # Major commercial
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MARIADB = "mariadb"
    ORACLE = "oracle"
    MSSQL = "mssql"
    DB2 = "db2"
    INFORMIX = "informix"
    SYBASE = "sybase"
    TERADATA = "teradata"
    VERTICA = "vertica"
    GREENPLUM = "greenplum"
    NETEZZA = "netezza"
    EXASOL = "exasol"
    SAP_HANA = "sap_hana"
    SAP_ASE = "sap_ase"

    # Open source
    SQLITE = "sqlite"
    FIREBIRD = "firebird"
    HSQLDB = "hsqldb"
    H2 = "h2"
    DERBY = "derby"
    DUCKDB = "duckdb"
    MONETDB = "monetdb"
    INGRES = "ingres"

    # NewSQL / Distributed SQL
    COCKROACHDB = "cockroachdb"
    TIDB = "tidb"
    YUGABYTEDB = "yugabytedb"
    VITESS = "vitess"
    SPANNER = "spanner"
    NUODB = "nuodb"
    VOLTDB = "voltdb"
    MEMSQL = "memsql"  # SingleStore
    SINGLESTORE = "singlestore"
    OCEANBASE = "oceanbase"
    POLARDB = "polardb"

    # =========================================================================
    # CLOUD-NATIVE SQL
    # =========================================================================
    PLANETSCALE = "planetscale"
    NEON = "neon"
    TURSO = "turso"
    XATA = "xata"
    SUPABASE_POSTGRES = "supabase_postgres"
    AURORA_POSTGRESQL = "aurora_postgresql"
    AURORA_MYSQL = "aurora_mysql"
    CLOUD_SQL = "cloud_sql"
    AZURE_SQL = "azure_sql"
    AZURE_SYNAPSE = "azure_synapse"
    ALLOYDB = "alloydb"
    CRUNCHY_BRIDGE = "crunchy_bridge"
    TIMESCALE_CLOUD = "timescale_cloud"
    TEMBO = "tembo"
    AIVEN = "aiven"
    ELEPHANTSQL = "elephantsql"
    HEROKU_POSTGRES = "heroku_postgres"
    RAILWAY_POSTGRES = "railway_postgres"
    RENDER_POSTGRES = "render_postgres"
    DIGITALOCEAN_MANAGED = "digitalocean_managed"

    # =========================================================================
    # NOSQL - DOCUMENT STORES
    # =========================================================================
    MONGODB = "mongodb"
    COUCHDB = "couchdb"
    COUCHBASE = "couchbase"
    FIRESTORE = "firestore"
    DYNAMODB = "dynamodb"
    COSMOSDB = "cosmosdb"
    FAUNA = "fauna"
    RAVENDB = "ravendb"
    MARKLOGIC = "marklogic"
    CLUSTERPOINT = "clusterpoint"
    RETHINKDB = "rethinkdb"
    POUCHDB = "pouchdb"
    LOWDB = "lowdb"
    NEDB = "nedb"
    LITEDB = "litedb"
    JSONSTORE = "jsonstore"
    TINYDB = "tinydb"

    # =========================================================================
    # NOSQL - KEY-VALUE STORES
    # =========================================================================
    REDIS = "redis"
    MEMCACHED = "memcached"
    ETCD = "etcd"
    VALKEY = "valkey"
    DRAGONFLY = "dragonfly"
    KEYDB = "keydb"
    AEROSPIKE = "aerospike"
    HAZELCAST = "hazelcast"
    IGNITE = "ignite"
    INFINISPAN = "infinispan"
    ORACLE_COHERENCE = "oracle_coherence"
    RIAK = "riak"
    VOLDEMORT = "voldemort"
    BERKELEY_DB = "berkeley_db"
    LEVELDB = "leveldb"
    ROCKSDB = "rocksdb"
    LMDB = "lmdb"
    BADGER = "badger"
    BOLT = "bolt"
    BBOLT = "bbolt"
    PEBBLE = "pebble"
    FOUNDATIONDB = "foundationdb"
    TIKV = "tikv"

    # =========================================================================
    # NOSQL - WIDE COLUMN STORES
    # =========================================================================
    CASSANDRA = "cassandra"
    SCYLLADB = "scylladb"
    HBASE = "hbase"
    BIGTABLE = "bigtable"
    ACCUMULO = "accumulo"
    HYPERTABLE = "hypertable"
    AZURE_TABLE = "azure_table"
    DYNAMODB_WIDE = "dynamodb_wide"

    # =========================================================================
    # NOSQL - GRAPH DATABASES
    # =========================================================================
    NEO4J = "neo4j"
    NEPTUNE = "neptune"
    ARANGODB = "arangodb"
    DGRAPH = "dgraph"
    JANUSGRAPH = "janusgraph"
    TIGERGRAPH = "tigergraph"
    ORIENTDB = "orientdb"
    MEMGRAPH = "memgraph"
    TERMINUSDB = "terminusdb"
    BLAZEGRAPH = "blazegraph"
    STARDOG = "stardog"
    GRAPHDB = "graphdb"
    VIRTUOSO = "virtuoso"
    ANZOGRAPH = "anzograph"
    NEBULA_GRAPH = "nebula_graph"
    HUGEGRAPH = "hugegraph"
    ARCADEDB = "arcadedb"
    SPARKSEE = "sparksee"
    INFINITEGRAPH = "infinitegraph"
    ALLEGRO_GRAPH = "allegro_graph"
    AMAZON_NEPTUNE = "amazon_neptune"

    # =========================================================================
    # TIME-SERIES DATABASES
    # =========================================================================
    TIMESCALEDB = "timescaledb"
    INFLUXDB = "influxdb"
    QUESTDB = "questdb"
    CLICKHOUSE = "clickhouse"
    PROMETHEUS = "prometheus"
    VICTORIAMETRICS = "victoriametrics"
    TDENGINE = "tdengine"
    APACHE_IOTDB = "apache_iotdb"
    OPENTSDB = "opentsdb"
    KAIROSDB = "kairosdb"
    GRAPHITE = "graphite"
    DRUID = "druid"
    PINOT = "pinot"
    KINETICA = "kinetica"
    CRATE_DB = "crate_db"
    GRIDDB = "griddb"
    MACHBASE = "machbase"
    AKUMULI = "akumuli"
    BERKELEYDB_TS = "berkeleydb_ts"
    EXTREMEDB = "extremedb"
    M3DB = "m3db"
    WARP10 = "warp10"
    HAWKULAR = "hawkular"
    AXIBASE = "axibase"

    # =========================================================================
    # VECTOR DATABASES (AI/ML)
    # =========================================================================
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    MILVUS = "milvus"
    QDRANT = "qdrant"
    CHROMA = "chroma"
    PGVECTOR = "pgvector"
    LANCEDB = "lancedb"
    VESPA = "vespa"
    VALD = "vald"
    FAISS = "faiss"
    ANNOY = "annoy"
    SCANN = "scann"
    HNSW = "hnsw"
    MARQO = "marqo"
    ZILLIZ = "zilliz"
    ACTIVELOOP = "activeloop"
    DEEP_LAKE = "deep_lake"
    VECTORDB = "vectordb"
    REDIS_VECTOR = "redis_vector"
    ELASTICSEARCH_VECTOR = "elasticsearch_vector"
    OPENSEARCH_VECTOR = "opensearch_vector"
    MONGODB_ATLAS_VECTOR = "mongodb_atlas_vector"
    SINGLESTORE_VECTOR = "singlestore_vector"
    SUPABASE_VECTOR = "supabase_vector"
    NEON_VECTOR = "neon_vector"

    # =========================================================================
    # SEARCH ENGINES
    # =========================================================================
    ELASTICSEARCH = "elasticsearch"
    OPENSEARCH = "opensearch"
    MEILISEARCH = "meilisearch"
    TYPESENSE = "typesense"
    ALGOLIA = "algolia"
    SOLR = "solr"
    SPHINX = "sphinx"
    MANTICORE = "manticore"
    SONIC = "sonic"
    ZINC = "zinc"
    QUICKWIT = "quickwit"
    TANTIVY = "tantivy"
    BLEVE = "bleve"
    REDISEARCH = "redisearch"
    WHOOSH = "whoosh"

    # =========================================================================
    # STREAMING / EVENT STORE DATABASES
    # =========================================================================
    KAFKA = "kafka"
    PULSAR = "pulsar"
    NATS = "nats"
    EVENTSTORE = "eventstore"
    AXONSERVER = "axonserver"
    MATERIALIZE = "materialize"
    KSQLDB = "ksqldb"
    RISINGWAVE = "risingwave"
    FLINK_SQL = "flink_sql"
    DATABEND = "databend"
    STARROCKS = "starrocks"
    DORIS = "doris"
    BYCONITY = "byconity"

    # =========================================================================
    # EMBEDDED DATABASES
    # =========================================================================
    SQLITE_EMBEDDED = "sqlite_embedded"
    DUCKDB_EMBEDDED = "duckdb_embedded"
    H2_EMBEDDED = "h2_embedded"
    DERBY_EMBEDDED = "derby_embedded"
    REALM = "realm"
    OBJECTBOX = "objectbox"
    HIVE_FLUTTER = "hive_flutter"
    ISAR_FLUTTER = "isar_flutter"
    NITRITE = "nitrite"
    MAPDB = "mapdb"
    XODUS = "xodus"
    MVSTORE = "mvstore"
    PREVAYLER = "prevayler"

    # =========================================================================
    # SPATIAL / GEO DATABASES
    # =========================================================================
    POSTGIS = "postgis"
    SPATIALITE = "spatialite"
    MONGODB_GEO = "mongodb_geo"
    ELASTICSEARCH_GEO = "elasticsearch_geo"
    GEOMESA = "geomesa"
    GEOWAVE = "geowave"
    CARTO = "carto"
    TILE38 = "tile38"

    # =========================================================================
    # OBJECT DATABASES
    # =========================================================================
    OBJECTDB = "objectdb"
    DB4O = "db4o"
    VERSANT = "versant"
    GEMSTONE = "gemstone"
    PERST = "perst"
    ZODB = "zodb"
    SIAQODB = "siaqodb"

    # =========================================================================
    # MULTI-MODEL DATABASES
    # =========================================================================
    FAUNA_MULTI = "fauna_multi"
    ARANGODB_MULTI = "arangodb_multi"
    ORIENTDB_MULTI = "orientdb_multi"
    COSMOSDB_MULTI = "cosmosdb_multi"
    COUCHBASE_MULTI = "couchbase_multi"
    MARKLOGIC_MULTI = "marklogic_multi"
    FOUNDATIONDB_MULTI = "foundationdb_multi"

    # =========================================================================
    # BLOCKCHAIN DATABASES
    # =========================================================================
    BIGCHAINDB = "bigchaindb"
    ORBITDB = "orbitdb"
    GUN = "gun"
    FLUREEDB = "flureedb"
    IMMUDB = "immudb"

    # =========================================================================
    # MAINFRAME DATABASES
    # =========================================================================
    IMS = "ims"
    IDMS = "idms"
    ADABAS = "adabas"
    VSAM = "vsam"
    DATACOM = "datacom"

    # =========================================================================
    # EDGE / MOBILE / OFFLINE-FIRST
    # =========================================================================
    POCKETBASE = "pocketbase"
    LIBSQL = "libsql"
    SQLD = "sqld"
    ELECTRIC_SQL = "electric_sql"
    WATERMELON_DB = "watermelon_db"
    RXDB = "rxdb"
    KINTO = "kinto"
    HOODIE = "hoodie"
    MINIMONGO = "minimongo"
    LOKIJS = "lokijs"

    # =========================================================================
    # ANALYTICS / OLAP
    # =========================================================================
    SNOWFLAKE = "snowflake"
    DATABRICKS = "databricks"
    REDSHIFT = "redshift"
    BIGQUERY = "bigquery"
    SYNAPSE = "synapse"
    FIREBOLT = "firebolt"
    MOTHERDUCK = "motherduck"
    DREMIO = "dremio"
    PRESTO = "presto"
    TRINO = "trino"
    ATHENA = "athena"
    STARBURST = "starburst"
    KYLIN = "kylin"
    CUBEJS = "cubejs"

    # =========================================================================
    # REALTIME DATABASES
    # =========================================================================
    FIREBASE_REALTIME = "firebase_realtime"
    SUPABASE_REALTIME = "supabase_realtime"
    RETHINKDB_REALTIME = "rethinkdb_realtime"
    CONVEX = "convex"
    LIVEBLOCKS = "liveblocks"
    YJS = "yjs"
    AUTOMERGE = "automerge"


class MigrationTool(Enum):
    """Supported migration tools - comprehensive list across 50+ languages."""
    # JavaScript/TypeScript ORMs
    PRISMA = "prisma"
    DRIZZLE = "drizzle"
    TYPEORM = "typeorm"
    SEQUELIZE = "sequelize"
    KNEX = "knex"
    MIKRO_ORM = "mikro_orm"
    OBJECTION = "objection"
    BOOKSHELF = "bookshelf"
    WATERLINE = "waterline"  # Sails.js
    MASSIVE = "massive"
    SLONIK = "slonik"
    ZAPATOS = "zapatos"
    KYSELY = "kysely"

    # Python ORMs
    ALEMBIC = "alembic"
    SQLALCHEMY = "sqlalchemy"
    DJANGO = "django"
    TORTOISE = "tortoise"
    PEEWEE = "peewee"
    SQLMODEL = "sqlmodel"
    PICCOLO = "piccolo"
    EDGEDB = "edgedb"
    ORATOR = "orator"
    PONY = "pony"
    SQLOBJECT = "sqlobject"
    STORM = "storm"
    YOYO = "yoyo"

    # Ruby
    RAILS_ACTIVERECORD = "rails_activerecord"
    SEQUEL = "sequel"
    ROM_RB = "rom_rb"
    HANAMI_MODEL = "hanami_model"
    STANDALONE_MIGRATIONS = "standalone_migrations"

    # PHP
    LARAVEL = "laravel"
    DOCTRINE = "doctrine"
    PHINX = "phinx"
    ELOQUENT = "eloquent"
    PROPEL = "propel"
    CYCLE_ORM = "cycle_orm"
    ATLAS = "atlas_php"
    IDIORM = "idiorm"
    REDBEAN = "redbean"

    # .NET / C#
    ENTITY_FRAMEWORK = "entity_framework"
    FLUENT_MIGRATOR = "fluent_migrator"
    DBUP = "dbup"
    ROUNDHOUSE = "roundhouse"
    DAPPER = "dapper"
    NHIBERNATE = "nhibernate"
    LINQ2DB = "linq2db"
    REPODB = "repodb"
    SERVICESTACK_ORMLITE = "servicestack_ormlite"
    EVOLVE = "evolve"

    # Java/JVM
    FLYWAY = "flyway"
    LIQUIBASE = "liquibase"
    MYBATIS = "mybatis"
    JOOQ = "jooq"
    HIBERNATE = "hibernate"
    EBEAN = "ebean"
    JDBI = "jdbi"
    SPRING_DATA = "spring_data"
    MICRONAUT_DATA = "micronaut_data"
    QUARKUS_PANACHE = "quarkus_panache"
    QUERYDSL = "querydsl"

    # Kotlin
    EXPOSED = "exposed"
    KTORM = "ktorm"
    KOMAPPER = "komapper"
    SQLDELIGHT = "sqldelight"
    JASYNC_SQL = "jasync_sql"

    # Scala
    SLICK = "slick"
    DOOBIE = "doobie"
    QUILL = "quill"
    SKUNK = "skunk"
    SCALIKEJDBC = "scalikejdbc"
    ANORM = "anorm"

    # Go
    GOOSE = "goose"
    GOLANG_MIGRATE = "golang_migrate"
    ATLAS_GO = "atlas"
    DBMATE = "dbmate"
    GORM = "gorm"
    ENT = "ent"
    SQLC = "sqlc"
    SQLBOILER = "sqlboiler"
    BUN = "bun_go"
    POP = "pop"
    REFORM = "reform"

    # Rust
    DIESEL = "diesel"
    SQLX = "sqlx"
    SEA_ORM = "sea_orm"
    REFINERY = "refinery"
    BARREL = "barrel"
    RBATIS = "rbatis"

    # Elixir
    ECTO = "ecto"
    OBAN = "oban"

    # Swift
    FLUENT_SWIFT = "fluent_swift"  # Vapor
    GRDB = "grdb"
    SQIFT = "sqift"

    # Dart/Flutter
    DRIFT = "drift"  # formerly Moor
    FLOOR = "floor"
    SQFLITE_MIGRATION = "sqflite_migration"
    HIVE = "hive"
    ISAR = "isar"

    # Clojure
    RAGTIME = "ragtime"
    MIGRATUS = "migratus"
    LOBOS = "lobos"
    JOPLIN = "joplin"

    # Haskell
    PERSISTENT = "persistent"
    BEAM = "beam"
    OPALEYE = "opaleye"
    HASQL = "hasql"
    ESQUELETO = "esqueleto"

    # F#
    DAPPER_FSHARP = "dapper_fsharp"
    SQLPROVIDER = "sqlprovider"
    DONALD = "donald"

    # Perl
    DBIX_CLASS = "dbix_class"
    ROSE_DB = "rose_db"
    DBIX_MIGRATION = "dbix_migration"

    # Lua
    LAPIS = "lapis"
    SAILOR = "sailor"

    # Julia
    SEARCHLIGHT = "searchlight"
    OCTO = "octo"

    # R
    DBPLYR = "dbplyr"
    DBITEST = "dbitest"

    # Crystal
    GRANITE = "granite"
    JENNIFER = "jennifer"
    CRECTO = "crecto"

    # Nim
    NORM = "norm"
    ORMIN = "ormin"

    # Zig
    ZIG_SQLITE = "zig_sqlite"

    # V
    VORM = "vorm"

    # OCaml
    CAQTI = "caqti"
    PETROL = "petrol"

    # Erlang
    BOSS_DB = "boss_db"
    SUMO_DB = "sumo_db"

    # C/C++
    SQLPP11 = "sqlpp11"
    ODB = "odb"
    SOCI = "soci"
    SQLITE_ORM = "sqlite_orm"
    POCO_DATA = "poco_data"

    # COBOL (still used in banking!)
    DB2_COBOL = "db2_cobol"
    ORACLE_PRO_COBOL = "oracle_pro_cobol"

    # Fortran (still used in scientific computing)
    POSTGRESQL_FORTRAN = "postgresql_fortran"

    # Database-specific managed services
    HASURA = "hasura"
    SUPABASE = "supabase"
    PLANETSCALE = "planetscale"
    NEON = "neon"
    TURSO = "turso"
    XATA = "xata"
    FAUNA = "fauna"
    COCKROACH = "cockroach"
    TIMESCALE = "timescale"

    # Schema-first / GraphQL
    GRAPHILE = "graphile"
    POSTGRAPHILE = "postgraphile"
    PRISMA_MIGRATE = "prisma_migrate"
    GRAPHQL_MESH = "graphql_mesh"

    # Online schema migration (zero-downtime)
    GH_OST = "gh_ost"  # GitHub's online schema migration
    PT_ONLINE_SCHEMA_CHANGE = "pt_online_schema_change"  # Percona
    SKEEMA = "skeema"
    SPIRIT = "spirit"
    LHM = "lhm"  # Large Hadron Migrator
    RESHAPE = "reshape"

    # NoSQL-specific
    MONGOCK = "mongock"  # MongoDB
    MIGRATE_MONGO = "migrate_mongo"
    CASSANDRA_MIGRATION = "cassandra_migration"
    DYNAMODB_MIGRATIONS = "dynamodb_migrations"
    REDIS_MIGRATIONS = "redis_migrations"

    # Schema validation
    SCHEMACRAWLER = "schemacrawler"
    SCHEMASPY = "schemaspy"

    # Raw SQL
    RAW_SQL = "raw_sql"


class MigrationDirection(Enum):
    """Migration direction."""
    UP = "up"
    DOWN = "down"


@dataclass
class MigrationInfo:
    """Information about a migration."""
    id: str
    name: str
    applied: bool
    applied_at: Optional[datetime] = None
    checksum: Optional[str] = None


@dataclass
class DatabaseBackup:
    """Database backup information."""
    id: str
    database: str
    created_at: datetime
    file_path: str
    size_bytes: int
    compressed: bool = False


@dataclass
class DatabaseResult:
    """Result of a database operation."""
    success: bool
    operation: str
    migrations_applied: List[str] = field(default_factory=list)
    migrations_rolled_back: List[str] = field(default_factory=list)
    backup_created: Optional[DatabaseBackup] = None
    output: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0
    rollback_command: Optional[str] = None


class DatabaseExecutorService:
    """
    Service for executing real database operations.

    Supports:
    - Running migrations (up/down)
    - Creating and restoring backups
    - Seeding data
    - Schema introspection
    - Connection testing
    """

    def __init__(self):
        self._operation_history: List[DatabaseResult] = []
        self._backups: Dict[str, DatabaseBackup] = {}

    def _get_command_env(self) -> dict:
        """
        Get environment for command execution with nvm compatibility fixes.
        Removes npm_config_prefix which conflicts with nvm.
        """
        env = os.environ.copy()
        env.pop("npm_config_prefix", None)  # Remove to fix nvm compatibility
        env["SHELL"] = env.get("SHELL", "/bin/bash")
        return env

    def _is_node_command(self, cmd: List[str]) -> bool:
        """Check if command requires Node.js environment."""
        if not cmd:
            return False
        node_commands = ["npm", "npx", "node", "yarn", "pnpm", "bun", "tsc", "next"]
        return cmd[0] in node_commands

    def _get_node_env_setup(self, workdir: Optional[str] = None) -> str:
        """Get Node.js environment setup commands for nvm/fnm/volta."""
        home = os.environ.get("HOME", os.path.expanduser("~"))
        setup_parts = []

        # Check for nvm
        nvm_dir = os.environ.get("NVM_DIR", os.path.join(home, ".nvm"))
        if os.path.exists(os.path.join(nvm_dir, "nvm.sh")):
            # Check for .nvmrc in workspace
            if workdir:
                nvmrc_path = os.path.join(workdir, ".nvmrc")
                node_version_path = os.path.join(workdir, ".node-version")
                if os.path.exists(nvmrc_path) or os.path.exists(node_version_path):
                    nvm_use = "nvm use 2>/dev/null || nvm install 2>/dev/null"
                else:
                    nvm_use = "nvm use default 2>/dev/null || true"
            else:
                nvm_use = "nvm use default 2>/dev/null || true"

            setup_parts.append(
                f'export NVM_DIR="{nvm_dir}" && '
                f'[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" --no-use 2>/dev/null && '
                f'{nvm_use}'
            )

        # Check for fnm
        fnm_path = os.path.join(home, ".fnm")
        if os.path.exists(fnm_path):
            setup_parts.append(f'export PATH="{fnm_path}:$PATH" && eval "$(fnm env 2>/dev/null)" 2>/dev/null || true')

        # Check for volta
        volta_home = os.environ.get("VOLTA_HOME", os.path.join(home, ".volta"))
        if os.path.exists(volta_home):
            setup_parts.append(f'export VOLTA_HOME="{volta_home}" && export PATH="$VOLTA_HOME/bin:$PATH"')

        return " && ".join(setup_parts) if setup_parts else ""

    async def detect_migration_tool(self, workspace_path: str) -> Optional[MigrationTool]:
        """Detect the migration tool used in the project."""
        workspace = Path(workspace_path)

        # Check for Prisma
        if (workspace / "prisma" / "schema.prisma").exists():
            return MigrationTool.PRISMA

        # Check for Drizzle
        if (workspace / "drizzle.config.ts").exists() or (workspace / "drizzle.config.js").exists():
            return MigrationTool.DRIZZLE

        # Check for Alembic (Python)
        if (workspace / "alembic.ini").exists():
            return MigrationTool.ALEMBIC

        # Check for Django
        if (workspace / "manage.py").exists():
            # Check if it's a Django project
            manage_content = (workspace / "manage.py").read_text()
            if "django" in manage_content.lower():
                return MigrationTool.DJANGO

        # Check for Knex
        if (workspace / "knexfile.js").exists() or (workspace / "knexfile.ts").exists():
            return MigrationTool.KNEX

        # Check for TypeORM
        if (workspace / "ormconfig.json").exists() or (workspace / "ormconfig.js").exists():
            return MigrationTool.TYPEORM

        # Check for Sequelize
        if (workspace / ".sequelizerc").exists():
            return MigrationTool.SEQUELIZE

        # Check for Flyway
        if (workspace / "flyway.conf").exists():
            return MigrationTool.FLYWAY

        # Check for Goose
        if any((workspace / "migrations").glob("*.sql")):
            return MigrationTool.GOOSE

        return None

    async def check_connection(
        self,
        connection_string: str,
        database_type: Optional[DatabaseType] = None,
    ) -> Tuple[bool, str]:
        """Test database connection."""
        # Infer database type from connection string if not provided
        if not database_type:
            if "postgresql" in connection_string or "postgres" in connection_string:
                database_type = DatabaseType.POSTGRESQL
            elif "mysql" in connection_string:
                database_type = DatabaseType.MYSQL
            elif "mongodb" in connection_string:
                database_type = DatabaseType.MONGODB
            elif "sqlite" in connection_string:
                database_type = DatabaseType.SQLITE

        try:
            if database_type == DatabaseType.POSTGRESQL:
                return await self._check_postgres_connection(connection_string)
            elif database_type == DatabaseType.MYSQL:
                return await self._check_mysql_connection(connection_string)
            elif database_type == DatabaseType.MONGODB:
                return await self._check_mongodb_connection(connection_string)
            elif database_type == DatabaseType.SQLITE:
                return await self._check_sqlite_connection(connection_string)
            else:
                return False, "Unknown database type"
        except Exception as e:
            return False, str(e)

    # -------------------------------------------------------------------------
    # Migration Operations
    # -------------------------------------------------------------------------

    async def run_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection = MigrationDirection.UP,
        target: Optional[str] = None,
        dry_run: bool = False,
        tool: Optional[MigrationTool] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> DatabaseResult:
        """
        Run database migrations.

        WARNING: This modifies the database schema!
        """
        result = DatabaseResult(
            success=False,
            operation=f"migration_{direction.value}",
        )

        start_time = datetime.utcnow()

        # Auto-detect tool if not specified
        if not tool:
            tool = await self.detect_migration_tool(workspace_path)
            if not tool:
                result.error = "Could not detect migration tool. Please specify one."
                return result

        if progress_callback:
            progress_callback(f"Running {tool.value} migrations ({direction.value})...", 20)

        # Execute based on tool
        executors = {
            MigrationTool.PRISMA: self._run_prisma_migrations,
            MigrationTool.DRIZZLE: self._run_drizzle_migrations,
            MigrationTool.ALEMBIC: self._run_alembic_migrations,
            MigrationTool.DJANGO: self._run_django_migrations,
            MigrationTool.KNEX: self._run_knex_migrations,
            MigrationTool.TYPEORM: self._run_typeorm_migrations,
            MigrationTool.SEQUELIZE: self._run_sequelize_migrations,
            MigrationTool.FLYWAY: self._run_flyway_migrations,
            MigrationTool.GOOSE: self._run_goose_migrations,
        }

        executor = executors.get(tool)
        if not executor:
            result.error = f"Migration tool {tool.value} not implemented"
            return result

        result = await executor(
            workspace_path,
            direction,
            target,
            dry_run,
            progress_callback,
        )

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    async def get_migration_status(
        self,
        workspace_path: str,
        tool: Optional[MigrationTool] = None,
    ) -> List[MigrationInfo]:
        """Get the status of all migrations."""
        if not tool:
            tool = await self.detect_migration_tool(workspace_path)

        if tool == MigrationTool.PRISMA:
            return await self._get_prisma_status(workspace_path)
        elif tool == MigrationTool.ALEMBIC:
            return await self._get_alembic_status(workspace_path)
        elif tool == MigrationTool.DJANGO:
            return await self._get_django_status(workspace_path)

        return []

    # -------------------------------------------------------------------------
    # Backup Operations
    # -------------------------------------------------------------------------

    async def create_backup(
        self,
        connection_string: str,
        database_name: str,
        output_dir: str,
        compress: bool = True,
        database_type: Optional[DatabaseType] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> DatabaseResult:
        """
        Create a database backup.

        Supports: PostgreSQL, MySQL, MongoDB
        """
        result = DatabaseResult(
            success=False,
            operation="backup",
        )

        start_time = datetime.utcnow()

        # Infer database type
        if not database_type:
            if "postgresql" in connection_string or "postgres" in connection_string:
                database_type = DatabaseType.POSTGRESQL
            elif "mysql" in connection_string:
                database_type = DatabaseType.MYSQL
            elif "mongodb" in connection_string:
                database_type = DatabaseType.MONGODB

        if progress_callback:
            progress_callback(f"Creating {database_type.value} backup...", 20)

        backup_file = Path(output_dir) / f"{database_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        try:
            if database_type == DatabaseType.POSTGRESQL:
                result = await self._backup_postgres(connection_string, database_name, backup_file, compress, progress_callback)
            elif database_type == DatabaseType.MYSQL:
                result = await self._backup_mysql(connection_string, database_name, backup_file, compress, progress_callback)
            elif database_type == DatabaseType.MONGODB:
                result = await self._backup_mongodb(connection_string, database_name, backup_file, compress, progress_callback)
            else:
                result.error = f"Backup not supported for {database_type.value}"
        except Exception as e:
            result.error = str(e)

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result

    async def restore_backup(
        self,
        connection_string: str,
        backup_file: str,
        database_type: Optional[DatabaseType] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> DatabaseResult:
        """
        Restore a database from backup.

        WARNING: This may overwrite existing data!
        """
        result = DatabaseResult(
            success=False,
            operation="restore",
        )

        start_time = datetime.utcnow()

        if progress_callback:
            progress_callback("Restoring database from backup...", 20)

        try:
            if database_type == DatabaseType.POSTGRESQL:
                result = await self._restore_postgres(connection_string, backup_file, progress_callback)
            elif database_type == DatabaseType.MYSQL:
                result = await self._restore_mysql(connection_string, backup_file, progress_callback)
            elif database_type == DatabaseType.MONGODB:
                result = await self._restore_mongodb(connection_string, backup_file, progress_callback)
            else:
                result.error = f"Restore not supported for {database_type.value if database_type else 'unknown'}"
        except Exception as e:
            result.error = str(e)

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result

    # -------------------------------------------------------------------------
    # Seeding Operations
    # -------------------------------------------------------------------------

    async def run_seeds(
        self,
        workspace_path: str,
        seed_file: Optional[str] = None,
        environment: str = "development",
        tool: Optional[MigrationTool] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> DatabaseResult:
        """
        Run database seeds.

        WARNING: This modifies data in the database!
        """
        result = DatabaseResult(
            success=False,
            operation="seed",
        )

        start_time = datetime.utcnow()

        if not tool:
            tool = await self.detect_migration_tool(workspace_path)

        if progress_callback:
            progress_callback("Running database seeds...", 20)

        if tool == MigrationTool.PRISMA:
            result = await self._run_prisma_seed(workspace_path, progress_callback)
        elif tool == MigrationTool.KNEX:
            result = await self._run_knex_seed(workspace_path, seed_file, progress_callback)
        elif tool == MigrationTool.DJANGO:
            result = await self._run_django_loaddata(workspace_path, seed_file, progress_callback)
        elif tool == MigrationTool.SEQUELIZE:
            result = await self._run_sequelize_seed(workspace_path, seed_file, progress_callback)
        else:
            result.error = f"Seeding not implemented for {tool.value if tool else 'unknown'}"

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self._operation_history.append(result)

        return result

    # -------------------------------------------------------------------------
    # Tool-Specific Migration Implementations
    # -------------------------------------------------------------------------

    async def _run_prisma_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection,
        target: Optional[str],
        dry_run: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Prisma migrations."""
        result = DatabaseResult(success=False, operation="prisma_migration")

        if direction == MigrationDirection.UP:
            cmd = ["npx", "prisma", "migrate", "deploy"]
        else:
            # Prisma doesn't have a direct "down" command, need to reset
            cmd = ["npx", "prisma", "migrate", "reset", "--force"]

        if dry_run:
            # For dry run, just show status
            cmd = ["npx", "prisma", "migrate", "status"]

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            # Parse applied migrations from output
            migrations = re.findall(r'(\d+_\w+)', output["stdout"])
            if direction == MigrationDirection.UP:
                result.migrations_applied = migrations
            else:
                result.migrations_rolled_back = migrations
            result.rollback_command = "npx prisma migrate reset --force"

            if progress_callback:
                progress_callback("Prisma migrations completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_drizzle_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection,
        target: Optional[str],
        dry_run: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Drizzle migrations."""
        result = DatabaseResult(success=False, operation="drizzle_migration")

        if direction == MigrationDirection.UP:
            cmd = ["npx", "drizzle-kit", "push:pg"]  # or mysql, sqlite
        else:
            cmd = ["npx", "drizzle-kit", "drop"]

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Drizzle migrations completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_alembic_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection,
        target: Optional[str],
        dry_run: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Alembic migrations."""
        result = DatabaseResult(success=False, operation="alembic_migration")

        if direction == MigrationDirection.UP:
            target_rev = target or "head"
            cmd = ["alembic", "upgrade", target_rev]
        else:
            target_rev = target or "-1"
            cmd = ["alembic", "downgrade", target_rev]

        if dry_run:
            cmd.append("--sql")

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            result.rollback_command = f"alembic downgrade -1"
            if progress_callback:
                progress_callback("Alembic migrations completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_django_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection,
        target: Optional[str],
        dry_run: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Django migrations."""
        result = DatabaseResult(success=False, operation="django_migration")

        if direction == MigrationDirection.UP:
            cmd = ["python", "manage.py", "migrate"]
            if target:
                cmd.append(target)
        else:
            # Django requires app name and migration number for rollback
            if not target:
                result.error = "Django rollback requires specifying app and migration (e.g., 'myapp 0001')"
                return result
            parts = target.split()
            cmd = ["python", "manage.py", "migrate", parts[0], parts[1] if len(parts) > 1 else "zero"]

        if dry_run:
            cmd.append("--plan")

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Django migrations completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_knex_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection,
        target: Optional[str],
        dry_run: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Knex migrations."""
        result = DatabaseResult(success=False, operation="knex_migration")

        if direction == MigrationDirection.UP:
            cmd = ["npx", "knex", "migrate:latest"]
        else:
            cmd = ["npx", "knex", "migrate:rollback"]

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            result.rollback_command = "npx knex migrate:rollback"
            if progress_callback:
                progress_callback("Knex migrations completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_typeorm_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection,
        target: Optional[str],
        dry_run: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run TypeORM migrations."""
        result = DatabaseResult(success=False, operation="typeorm_migration")

        if direction == MigrationDirection.UP:
            cmd = ["npx", "typeorm", "migration:run"]
        else:
            cmd = ["npx", "typeorm", "migration:revert"]

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            result.rollback_command = "npx typeorm migration:revert"
            if progress_callback:
                progress_callback("TypeORM migrations completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_sequelize_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection,
        target: Optional[str],
        dry_run: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Sequelize migrations."""
        result = DatabaseResult(success=False, operation="sequelize_migration")

        if direction == MigrationDirection.UP:
            cmd = ["npx", "sequelize-cli", "db:migrate"]
        else:
            cmd = ["npx", "sequelize-cli", "db:migrate:undo"]
            if target == "all":
                cmd = ["npx", "sequelize-cli", "db:migrate:undo:all"]

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            result.rollback_command = "npx sequelize-cli db:migrate:undo"
            if progress_callback:
                progress_callback("Sequelize migrations completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_flyway_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection,
        target: Optional[str],
        dry_run: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Flyway migrations."""
        result = DatabaseResult(success=False, operation="flyway_migration")

        if direction == MigrationDirection.UP:
            cmd = ["flyway", "migrate"]
        else:
            cmd = ["flyway", "undo"]

        if dry_run:
            cmd = ["flyway", "info"]

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Flyway migrations completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_goose_migrations(
        self,
        workspace_path: str,
        direction: MigrationDirection,
        target: Optional[str],
        dry_run: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Goose migrations."""
        result = DatabaseResult(success=False, operation="goose_migration")

        db_string = os.environ.get("DATABASE_URL", "")

        if direction == MigrationDirection.UP:
            cmd = ["goose", "-dir", "migrations", "postgres", db_string, "up"]
        else:
            cmd = ["goose", "-dir", "migrations", "postgres", db_string, "down"]

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Goose migrations completed", 100)
        else:
            result.error = output["stderr"]

        return result

    # -------------------------------------------------------------------------
    # Status Methods
    # -------------------------------------------------------------------------

    async def _get_prisma_status(self, workspace_path: str) -> List[MigrationInfo]:
        """Get Prisma migration status."""
        migrations = []
        output = await self._run_command(
            ["npx", "prisma", "migrate", "status"],
            cwd=workspace_path
        )

        # Parse output for migration info
        for line in output["stdout"].split("\n"):
            if "applied" in line.lower() or "pending" in line.lower():
                parts = line.split()
                if len(parts) >= 2:
                    migrations.append(MigrationInfo(
                        id=parts[0],
                        name=parts[0],
                        applied="applied" in line.lower(),
                    ))

        return migrations

    async def _get_alembic_status(self, workspace_path: str) -> List[MigrationInfo]:
        """Get Alembic migration status."""
        migrations = []
        output = await self._run_command(
            ["alembic", "history", "--verbose"],
            cwd=workspace_path
        )

        current = await self._run_command(
            ["alembic", "current"],
            cwd=workspace_path
        )
        current_rev = current["stdout"].strip().split()[0] if current["stdout"] else ""

        for line in output["stdout"].split("\n"):
            match = re.match(r'([a-f0-9]+)\s+.*->\s+([a-f0-9]+)', line)
            if match:
                rev = match.group(2)
                migrations.append(MigrationInfo(
                    id=rev,
                    name=line,
                    applied=rev <= current_rev if current_rev else False,
                ))

        return migrations

    async def _get_django_status(self, workspace_path: str) -> List[MigrationInfo]:
        """Get Django migration status."""
        migrations = []
        output = await self._run_command(
            ["python", "manage.py", "showmigrations", "--list"],
            cwd=workspace_path
        )

        for line in output["stdout"].split("\n"):
            if "[X]" in line or "[ ]" in line:
                applied = "[X]" in line
                name = line.replace("[X]", "").replace("[ ]", "").strip()
                migrations.append(MigrationInfo(
                    id=name,
                    name=name,
                    applied=applied,
                ))

        return migrations

    # -------------------------------------------------------------------------
    # Backup Implementations
    # -------------------------------------------------------------------------

    async def _backup_postgres(
        self,
        connection_string: str,
        database_name: str,
        backup_file: Path,
        compress: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Create PostgreSQL backup using pg_dump."""
        result = DatabaseResult(success=False, operation="postgres_backup")

        output_file = f"{backup_file}.sql"
        if compress:
            output_file = f"{backup_file}.sql.gz"

        cmd = ["pg_dump", connection_string, "-f", output_file if not compress else "-"]

        if compress:
            # Pipe through gzip
            proc1 = await asyncio.create_subprocess_exec(
                "pg_dump", connection_string,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            proc2 = await asyncio.create_subprocess_exec(
                "gzip",
                stdin=proc1.stdout,
                stdout=open(output_file, 'wb'),
                stderr=asyncio.subprocess.PIPE,
            )
            await proc2.wait()
            returncode = proc2.returncode
        else:
            output = await self._run_command(cmd)
            returncode = output["returncode"]

        if returncode == 0:
            result.success = True
            file_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
            result.backup_created = DatabaseBackup(
                id=str(datetime.utcnow().timestamp()),
                database=database_name,
                created_at=datetime.utcnow(),
                file_path=output_file,
                size_bytes=file_size,
                compressed=compress,
            )
            result.rollback_command = f"psql {connection_string} < {output_file}"

            if progress_callback:
                progress_callback(f"Backup created: {output_file}", 100)
        else:
            result.error = "pg_dump failed"

        return result

    async def _backup_mysql(
        self,
        connection_string: str,
        database_name: str,
        backup_file: Path,
        compress: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Create MySQL backup using mysqldump."""
        result = DatabaseResult(success=False, operation="mysql_backup")

        # Parse connection string for credentials
        # Format: mysql://user:pass@host:port/database

        output_file = f"{backup_file}.sql"
        if compress:
            output_file = f"{backup_file}.sql.gz"

        cmd = ["mysqldump", "--single-transaction", database_name]

        if not compress:
            cmd.extend(["-r", output_file])

        output = await self._run_command(cmd)

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback(f"MySQL backup created: {output_file}", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _backup_mongodb(
        self,
        connection_string: str,
        database_name: str,
        backup_file: Path,
        compress: bool,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Create MongoDB backup using mongodump."""
        result = DatabaseResult(success=False, operation="mongodb_backup")

        output_dir = str(backup_file)

        cmd = ["mongodump", "--uri", connection_string, "--out", output_dir]

        if compress:
            cmd.append("--gzip")

        output = await self._run_command(cmd)

        if output["returncode"] == 0:
            result.success = True
            result.rollback_command = f"mongorestore --uri {connection_string} {output_dir}"

            if progress_callback:
                progress_callback(f"MongoDB backup created: {output_dir}", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _restore_postgres(
        self,
        connection_string: str,
        backup_file: str,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Restore PostgreSQL from backup."""
        result = DatabaseResult(success=False, operation="postgres_restore")

        if backup_file.endswith(".gz"):
            # Decompress and restore
            cmd = f"gunzip -c {backup_file} | psql {connection_string}"
            output = await self._run_shell_command(cmd)
        else:
            output = await self._run_command(["psql", connection_string, "-f", backup_file])

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("PostgreSQL restored from backup", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _restore_mysql(
        self,
        connection_string: str,
        backup_file: str,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Restore MySQL from backup."""
        result = DatabaseResult(success=False, operation="mysql_restore")

        if backup_file.endswith(".gz"):
            cmd = f"gunzip -c {backup_file} | mysql"
        else:
            cmd = f"mysql < {backup_file}"

        output = await self._run_shell_command(cmd)

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("MySQL restored from backup", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _restore_mongodb(
        self,
        connection_string: str,
        backup_file: str,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Restore MongoDB from backup."""
        result = DatabaseResult(success=False, operation="mongodb_restore")

        cmd = ["mongorestore", "--uri", connection_string, backup_file]

        output = await self._run_command(cmd)

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("MongoDB restored from backup", 100)
        else:
            result.error = output["stderr"]

        return result

    # -------------------------------------------------------------------------
    # Seed Implementations
    # -------------------------------------------------------------------------

    async def _run_prisma_seed(
        self,
        workspace_path: str,
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Prisma seed."""
        result = DatabaseResult(success=False, operation="prisma_seed")

        output = await self._run_command(
            ["npx", "prisma", "db", "seed"],
            cwd=workspace_path
        )
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Prisma seed completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_knex_seed(
        self,
        workspace_path: str,
        seed_file: Optional[str],
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Knex seed."""
        result = DatabaseResult(success=False, operation="knex_seed")

        cmd = ["npx", "knex", "seed:run"]
        if seed_file:
            cmd.extend(["--specific", seed_file])

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Knex seed completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_django_loaddata(
        self,
        workspace_path: str,
        fixture: Optional[str],
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Django loaddata."""
        result = DatabaseResult(success=False, operation="django_loaddata")

        if not fixture:
            result.error = "Django loaddata requires a fixture file"
            return result

        output = await self._run_command(
            ["python", "manage.py", "loaddata", fixture],
            cwd=workspace_path
        )
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Django loaddata completed", 100)
        else:
            result.error = output["stderr"]

        return result

    async def _run_sequelize_seed(
        self,
        workspace_path: str,
        seed_file: Optional[str],
        progress_callback: Optional[Callable[[str, float], None]],
    ) -> DatabaseResult:
        """Run Sequelize seed."""
        result = DatabaseResult(success=False, operation="sequelize_seed")

        cmd = ["npx", "sequelize-cli", "db:seed:all"]
        if seed_file:
            cmd = ["npx", "sequelize-cli", "db:seed", "--seed", seed_file]

        output = await self._run_command(cmd, cwd=workspace_path)
        result.output = output["stdout"]

        if output["returncode"] == 0:
            result.success = True
            if progress_callback:
                progress_callback("Sequelize seed completed", 100)
        else:
            result.error = output["stderr"]

        return result

    # -------------------------------------------------------------------------
    # Connection Check Methods
    # -------------------------------------------------------------------------

    async def _check_postgres_connection(self, connection_string: str) -> Tuple[bool, str]:
        """Check PostgreSQL connection."""
        output = await self._run_command(["psql", connection_string, "-c", "SELECT 1"])
        if output["returncode"] == 0:
            return True, "PostgreSQL connection successful"
        return False, output["stderr"]

    async def _check_mysql_connection(self, connection_string: str) -> Tuple[bool, str]:
        """Check MySQL connection."""
        output = await self._run_command(["mysql", "-e", "SELECT 1"])
        if output["returncode"] == 0:
            return True, "MySQL connection successful"
        return False, output["stderr"]

    async def _check_mongodb_connection(self, connection_string: str) -> Tuple[bool, str]:
        """Check MongoDB connection."""
        output = await self._run_command(["mongosh", connection_string, "--eval", "db.runCommand({ping:1})"])
        if output["returncode"] == 0:
            return True, "MongoDB connection successful"
        return False, output["stderr"]

    async def _check_sqlite_connection(self, connection_string: str) -> Tuple[bool, str]:
        """Check SQLite connection."""
        db_path = connection_string.replace("sqlite:///", "").replace("sqlite://", "")
        if os.path.exists(db_path):
            return True, f"SQLite database exists: {db_path}"
        return False, f"SQLite database not found: {db_path}"

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    async def _run_command(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a command and return the result."""
        try:
            env = self._get_command_env()

            # For node commands, use shell with nvm setup
            if self._is_node_command(cmd):
                env_setup = self._get_node_env_setup(cwd)
                cmd_str = " ".join(cmd)
                if env_setup:
                    full_cmd = f"unset npm_config_prefix 2>/dev/null; {env_setup} && {cmd_str}"
                else:
                    full_cmd = f"unset npm_config_prefix 2>/dev/null; {cmd_str}"

                process = await asyncio.create_subprocess_shell(
                    full_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                    executable="/bin/bash",
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )

            stdout, stderr = await process.communicate()

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
        except Exception as e:
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(e),
            }

    async def _run_shell_command(self, cmd: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """Run a shell command."""
        try:
            env = self._get_command_env()

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
                executable="/bin/bash",
            )

            stdout, stderr = await process.communicate()

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
        except Exception as e:
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(e),
            }


# Global instance
database_executor_service = DatabaseExecutorService()
