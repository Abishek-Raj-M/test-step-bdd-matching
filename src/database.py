"""Database module for PostgreSQL with pgvector."""
import psycopg2
from psycopg2.extras import execute_values
from psycopg2.extensions import register_adapter, AsIs
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json


# Register numpy array adapter for pgvector
def adapt_numpy_array(arr):
    """Adapt numpy array for pgvector."""
    return AsIs("'[" + ",".join(str(x) for x in arr) + "]'::vector")


register_adapter(np.ndarray, adapt_numpy_array)


@dataclass
class TestStepChunk:
    """Test step chunk data."""
    chunk_id: str
    parent_testcase_id: str
    original_chunk: str
    normalized_chunk: str
    action_verb: Optional[str]
    primary_object: Optional[str]
    placeholders: List[Dict[str, Any]]
    cluster_id: Optional[int]
    chunk_index: int
    normalization_version: str


@dataclass
class FeatureStep:
    """BDD Step (Given/When/Then scenario)."""
    id: Optional[int]
    testcase_id: str
    bdd_step: str  # Full BDD text
    bdd_step_normalized: str
    scenario_name: Optional[str]
    given_steps: Optional[str]
    when_steps: Optional[str]
    then_steps: Optional[str]
    usage_count: int = 0


@dataclass
class IndividualBDDStep:
    """Individual BDD step (single Given/When/Then)."""
    id: Optional[int]
    feature_step_id: int  # Link to parent scenario
    step_type: str  # 'Given', 'When', or 'Then'
    step_text: str  # The actual step text
    step_text_normalized: str
    step_index: int  # Order within scenario
    embedding: np.ndarray
    usage_count: int = 0


class Database:
    """Database interface for teststep_rag system."""
    
    def __init__(self, config):
        self.config = config
        self.table_chunks = "teststep_chunks"
        self.table_feature_steps = "feature_steps"
        self.table_individual_steps = "bdd_individual_steps"
        self.conn = None
        self._connect()
        self._ensure_extensions()
        self._create_schema()
    
    def _connect(self):
        """Connect to PostgreSQL database."""
        self.conn = psycopg2.connect(
            host=self.config.database.host,
            port=self.config.database.port,
            database=self.config.database.database,
            user=self.config.database.user,
            password=self.config.database.password
        )
        self.conn.autocommit = True
    
    def _ensure_extensions(self):
        """Ensure pgvector extension is installed."""
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    def _create_schema(self):
        """Create database schema."""
        with self.conn.cursor() as cur:
            # Create teststep_chunks table (no embedding - not used for matching)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS {table_chunks} (
                    chunk_id SERIAL PRIMARY KEY,
                    parent_testcase_id VARCHAR(255),
                    original_chunk TEXT NOT NULL,
                    normalized_chunk TEXT NOT NULL,
                    action_verb VARCHAR(100),
                    primary_object VARCHAR(255),
                    placeholders JSONB,
                    cluster_id INTEGER,
                    chunk_index INTEGER,
                    normalization_version VARCHAR(10),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """.format(table_chunks=self.table_chunks))
            
            # Create indexes for joins
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_{table_chunks}_cluster_id 
                ON {table_chunks}(cluster_id);
            """.format(table_chunks=self.table_chunks))
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_{table_chunks}_parent_id 
                ON {table_chunks}(parent_testcase_id);
            """.format(table_chunks=self.table_chunks))
            
            # Create feature_steps table - stores actual BDD Steps (no embedding - not used for matching)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS {feature_steps} (
                    id SERIAL PRIMARY KEY,
                    testcase_id VARCHAR(255),
                    bdd_step TEXT NOT NULL,
                    bdd_step_normalized TEXT,
                    scenario_name VARCHAR(500),
                    given_steps TEXT,
                    when_steps TEXT,
                    then_steps TEXT,
                    doc_tsv TSVECTOR,
                    usage_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """.format(feature_steps=self.table_feature_steps))
            
            # Add bdd_step_id column to teststep_chunks if not exists
            cur.execute(f"""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='{self.table_chunks}' AND column_name='bdd_step_id') THEN
                        EXECUTE 'ALTER TABLE {self.table_chunks} ADD COLUMN bdd_step_id INTEGER REFERENCES {self.table_feature_steps}(id);';
                    END IF;
                END $$;
            """)
            
            # Create GIN index for lexical search
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_{feature_steps}_tsv 
                ON {feature_steps} 
                USING GIN (doc_tsv);
            """.format(feature_steps=self.table_feature_steps))
            
            # Create index for testcase_id lookup
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_{feature_steps}_testcase_id 
                ON {feature_steps}(testcase_id);
            """.format(feature_steps=self.table_feature_steps))
            
            # Create bdd_individual_steps table - stores individual Given/When/Then steps
            cur.execute("""
                CREATE TABLE IF NOT EXISTS {individual_steps} (
                    id SERIAL PRIMARY KEY,
                    feature_step_id INTEGER NOT NULL REFERENCES {feature_steps}(id) ON DELETE CASCADE,
                    step_type VARCHAR(10) NOT NULL,  -- 'Given', 'When', or 'Then'
                    step_text TEXT NOT NULL,
                    step_text_normalized TEXT,
                    step_index INTEGER NOT NULL,
                    embedding vector(%s),
                    doc_tsv TSVECTOR,
                    usage_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """.format(individual_steps=self.table_individual_steps, feature_steps=self.table_feature_steps), (self.config.embedding.dim,))
            
            # Create HNSW index for individual steps
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_{individual_steps}_embedding 
                ON {individual_steps} 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """.format(individual_steps=self.table_individual_steps))
            
            # Create GIN index for lexical search
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_{individual_steps}_tsv 
                ON {individual_steps} 
                USING GIN (doc_tsv);
            """.format(individual_steps=self.table_individual_steps))
            
            # Create indexes for joins
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_{individual_steps}_feature_id 
                ON {individual_steps}(feature_step_id);
            """.format(individual_steps=self.table_individual_steps))
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_{individual_steps}_type 
                ON {individual_steps}(step_type);
            """.format(individual_steps=self.table_individual_steps))
    
    def insert_chunk(self, chunk: TestStepChunk) -> int:
        """Insert a test step chunk."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO {table_chunks} 
                (parent_testcase_id, original_chunk, normalized_chunk, action_verb, 
                 primary_object, placeholders, cluster_id, chunk_index, normalization_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING chunk_id;
            """.format(table_chunks=self.table_chunks), (
                chunk.parent_testcase_id,
                chunk.original_chunk,
                chunk.normalized_chunk,
                chunk.action_verb,
                chunk.primary_object,
                json.dumps(chunk.placeholders),
                chunk.cluster_id,
                chunk.chunk_index,
                chunk.normalization_version
            ))
            return cur.fetchone()[0]
    
    def insert_chunks_batch(self, chunks: List[TestStepChunk]):
        """Insert chunks in batch."""
        with self.conn.cursor() as cur:
            data = [(
                chunk.parent_testcase_id,
                chunk.original_chunk,
                chunk.normalized_chunk,
                chunk.action_verb,
                chunk.primary_object,
                json.dumps(chunk.placeholders),
                chunk.cluster_id,
                chunk.chunk_index,
                chunk.normalization_version
            ) for chunk in chunks]
            
            execute_values(
                cur,
                """
                INSERT INTO {table_chunks} 
                (parent_testcase_id, original_chunk, normalized_chunk, action_verb, 
                 primary_object, placeholders, cluster_id, chunk_index, normalization_version)
                VALUES %s;
                """.format(table_chunks=self.table_chunks),
                data
            )
    
    def update_cluster_ids(self, chunk_ids: List[int], cluster_id: int):
        """Update cluster_id for chunks."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE {table_chunks} 
                SET cluster_id = %s, updated_at = NOW()
                WHERE chunk_id = ANY(%s);
            """.format(table_chunks=self.table_chunks), (cluster_id, chunk_ids))
    
    def insert_feature_step(self, feature_step: FeatureStep) -> int:
        """Insert a BDD step (Given/When/Then scenario)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO {feature_steps} 
                (testcase_id, bdd_step, bdd_step_normalized, scenario_name, 
                 given_steps, when_steps, then_steps, doc_tsv, usage_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, to_tsvector('english', %s), %s)
                RETURNING id;
            """.format(feature_steps=self.table_feature_steps), (
                feature_step.testcase_id,
                feature_step.bdd_step,
                feature_step.bdd_step_normalized,
                feature_step.scenario_name,
                feature_step.given_steps,
                feature_step.when_steps,
                feature_step.then_steps,
                feature_step.bdd_step,
                feature_step.usage_count
            ))
            return cur.fetchone()[0]
    
    def update_chunk_bdd_step(self, chunk_id: int, bdd_step_id: int):
        """Link a chunk to its BDD step."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE {table_chunks} 
                SET bdd_step_id = %s, updated_at = NOW()
                WHERE chunk_id = %s;
            """.format(table_chunks=self.table_chunks), (bdd_step_id, chunk_id))
    
    def insert_individual_bdd_step(self, individual_step: IndividualBDDStep) -> int:
        """Insert an individual BDD step (Given/When/Then)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO {individual_steps} 
                (feature_step_id, step_type, step_text, step_text_normalized, 
                 step_index, embedding, doc_tsv, usage_count)
                VALUES (%s, %s, %s, %s, %s, %s, to_tsvector('english', %s), %s)
                RETURNING id;
            """.format(individual_steps=self.table_individual_steps), (
                individual_step.feature_step_id,
                individual_step.step_type,
                individual_step.step_text,
                individual_step.step_text_normalized,
                individual_step.step_index,
                individual_step.embedding.tolist(),
                individual_step.step_text,
                individual_step.usage_count
            ))
            return cur.fetchone()[0]
    
    def get_feature_step_by_id(self, feature_step_id: int) -> Optional[FeatureStep]:
        """Get a feature step (scenario) by ID."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, testcase_id, bdd_step, bdd_step_normalized, scenario_name,
                       given_steps, when_steps, then_steps, usage_count
                FROM {feature_steps}
                WHERE id = %s;
            """.format(feature_steps=self.table_feature_steps), (feature_step_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return FeatureStep(
                id=row[0],
                testcase_id=row[1],
                bdd_step=row[2],
                bdd_step_normalized=row[3],
                scenario_name=row[4],
                given_steps=row[5],
                when_steps=row[6],
                then_steps=row[7],
                usage_count=row[8]
            )
    
    def vector_search(self, query_embedding: np.ndarray, limit: int, ef_search: int) -> List[Tuple[int, float, Dict[str, Any]]]:
        """Perform vector similarity search on individual BDD steps."""
        with self.conn.cursor() as cur:
            # Set ef_search parameter
            cur.execute(f"SET LOCAL hnsw.ef_search = {ef_search};")
            
            # Search individual steps and join with parent scenario
            cur.execute("""
                SELECT 
                    bis.id,
                    bis.feature_step_id,
                    bis.step_type,
                    bis.step_text,
                    bis.step_text_normalized,
                    bis.step_index,
                    bis.usage_count,
                    fs.id as scenario_id,
                    fs.testcase_id,
                    fs.bdd_step,
                    fs.scenario_name,
                    fs.given_steps,
                    fs.when_steps,
                    fs.then_steps,
                    1 - (bis.embedding <=> %s::vector) as similarity
                FROM {individual_steps} bis
                JOIN {feature_steps} fs ON bis.feature_step_id = fs.id
                ORDER BY bis.embedding <=> %s::vector
                LIMIT %s;
            """.format(individual_steps=self.table_individual_steps, feature_steps=self.table_feature_steps), (query_embedding.tolist(), query_embedding.tolist(), limit))
            
            results = []
            for row in cur.fetchall():
                results.append((
                    row[0],  # individual step id
                    row[14],  # similarity
                    {
                        "id": row[0],  # individual step id
                        "feature_step_id": row[1],
                        "step_type": row[2],
                        "step_text": row[3],
                        "step_text_normalized": row[4],
                        "step_index": row[5],
                        "usage_count": row[6],
                        # Full scenario context
                        "scenario_id": row[7],
                        "scenario_testcase_id": row[8],
                        "scenario_full_text": row[9],
                        "scenario_name": row[10],
                        "scenario_given_steps": row[11],
                        "scenario_when_steps": row[12],
                        "scenario_then_steps": row[13],
                        # For backwards compatibility
                        "normalized_text": row[4],
                        "bdd_step": row[9]  # Full scenario text
                    }
                ))
            return results
    
    def lexical_search(self, query_text: str, limit: int) -> List[Tuple[int, float, Dict[str, Any]]]:
        """Perform lexical search using tsvector."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, testcase_id, bdd_step, bdd_step_normalized, scenario_name,
                       given_steps, when_steps, then_steps, usage_count,
                       ts_rank(doc_tsv, plainto_tsquery('english', %s)) as rank
                FROM {feature_steps}
                WHERE doc_tsv @@ plainto_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s;
            """.format(feature_steps=self.table_feature_steps), (query_text, query_text, limit))
            
            results = []
            for row in cur.fetchall():
                results.append((
                    row[0],  # id
                    row[9] if row[9] else 0.0,  # rank
                    {
                        "id": row[0],
                        "testcase_id": row[1],
                        "bdd_step": row[2],
                        "canonical_template": row[2],  # For backwards compatibility
                        "normalized_text": row[3],
                        "scenario_name": row[4],
                        "given_steps": row[5],
                        "when_steps": row[6],
                        "then_steps": row[7],
                        "usage_count": row[8]
                    }
                ))
            return results
    
    def get_chunks_by_cluster(self, cluster_id: int) -> List[Dict[str, Any]]:
        """Get all chunks in a cluster."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT chunk_id, original_chunk, normalized_chunk, action_verb, primary_object
                FROM {table_chunks}
                WHERE cluster_id = %s
                ORDER BY chunk_index;
            """.format(table_chunks=self.table_chunks), (cluster_id,))
            
            results = []
            for row in cur.fetchall():
                results.append({
                    "chunk_id": row[0],
                    "original_chunk": row[1],
                    "normalized_chunk": row[2],
                    "action_verb": row[3],
                    "primary_object": row[4]
                })
            return results
    
    def get_chunk_by_id(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """Get a single chunk by ID."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT chunk_id, original_chunk, normalized_chunk, action_verb, primary_object
                FROM {table_chunks}
                WHERE chunk_id = %s;
            """.format(table_chunks=self.table_chunks), (chunk_id,))
            
            row = cur.fetchone()
            if row:
                return {
                    "chunk_id": row[0],
                    "original_chunk": row[1],
                    "normalized_chunk": row[2],
                    "action_verb": row[3],
                    "primary_object": row[4]
                }
            return None
    
    def get_all_chunks_for_clustering(self) -> List[Tuple[int, np.ndarray, str]]:
        """Get all chunks with embeddings for clustering."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT chunk_id, embedding::text, normalized_chunk
                FROM {table_chunks}
                WHERE cluster_id IS NULL;
            """.format(table_chunks=self.table_chunks))
            
            results = []
            for row in cur.fetchall():
                # Parse vector string format: [0.1,0.2,0.3,...] to numpy array
                embedding_str = row[1]
                if embedding_str:
                    # Remove brackets and split by comma
                    embedding_str = embedding_str.strip('[]')
                    embedding = np.array([float(x) for x in embedding_str.split(',')])
                    results.append((row[0], embedding, row[2]))
            return results
    
    def increment_usage_count(self, feature_step_id: int):
        """Increment usage count for a feature step (scenario)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE {feature_steps} 
                SET usage_count = usage_count + 1, updated_at = NOW()
                WHERE id = %s;
            """.format(feature_steps=self.table_feature_steps), (feature_step_id,))
    
    def increment_individual_step_usage(self, individual_step_id: int):
        """Increment usage count for an individual BDD step."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE {individual_steps} 
                SET usage_count = usage_count + 1, updated_at = NOW()
                WHERE id = %s;
            """.format(individual_steps=self.table_individual_steps), (individual_step_id,))
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

