"""Ingestion pipeline for loading test steps into database."""
import csv
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np
from tqdm import tqdm

from src.database import Database, TestStepChunk, FeatureStep, IndividualBDDStep
from src.normalizer import Normalizer
from src.chunker import Chunker
from src.embedder import Embedder
from src.bdd_parser import BDDParser


class IngestionPipeline:
    """Ingests test steps from CSV/JSON into database."""
    
    def __init__(self, config, database, normalizer, chunker, embedder):
        self.config = config
        self.db = database
        self.normalizer = normalizer
        self.chunker = chunker
        self.embedder = embedder
        self.bdd_parser = BDDParser()
    
    def ingest_csv_with_bdd(self, csv_path: str, testcase_id_col: str = "ID", 
                           steps_col: str = "Manual Steps", bdd_col: str = "BDD Steps"):
        """
        Ingest test steps WITH their corresponding BDD Steps.
        
        This creates:
        1. feature_steps: Actual BDD Steps (Given/When/Then scenarios)
        2. teststep_chunks: Manual step chunks linked to their BDD step
        
        Args:
            csv_path: Path to CSV file
            testcase_id_col: Column name for test case ID
            steps_col: Column name for manual steps
            bdd_col: Column name for BDD steps
        """
        # First pass: count rows
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            total_rows = sum(1 for _ in csv.DictReader(f))
        
        print(f"\n{'='*60}")
        print(f"Ingesting: {csv_path}")
        print(f"Total rows: {total_rows}")
        print(f"{'='*60}")
        
        bdd_count = 0
        chunk_count = 0
        skipped_no_bdd = 0
        
        # Use utf-8-sig to handle BOM (Byte Order Mark) in CSV files
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            pbar = tqdm(reader, total=total_rows, desc="Processing", unit="row")
            
            for row in pbar:
                testcase_id = row.get(testcase_id_col, '')
                manual_steps = row.get(steps_col, '')
                bdd_steps = row.get(bdd_col, '')
                
                if not manual_steps or not testcase_id:
                    continue
                
                # Skip if no BDD steps
                if not bdd_steps or not bdd_steps.strip():
                    skipped_no_bdd += 1
                    continue
                
                # Step 1: Parse and store BDD Step
                parsed_bdd = self.bdd_parser.parse(bdd_steps)
                
                # Get searchable text for embedding
                bdd_searchable = self.bdd_parser.get_searchable_text(parsed_bdd)
                bdd_normalized = self.normalizer.normalize(bdd_searchable)
                bdd_embedding = self.embedder.embed(bdd_normalized.normalized_text)
                
                # Create and insert feature step (BDD)
                feature_step = FeatureStep(
                    id=None,
                    testcase_id=testcase_id,
                    bdd_step=bdd_steps,
                    bdd_step_normalized=bdd_normalized.normalized_text,
                    scenario_name=parsed_bdd.scenario_name,
                    given_steps=parsed_bdd.given_steps,
                    when_steps=parsed_bdd.when_steps,
                    then_steps=parsed_bdd.then_steps,
                    embedding=bdd_embedding,
                    usage_count=0
                )
                
                bdd_step_id = self.db.insert_feature_step(feature_step)
                bdd_count += 1
                
                # Step 1.5: Extract and store individual BDD steps (Given/When/Then)
                individual_steps = self.bdd_parser.extract_individual_steps(bdd_steps)
                individual_step_texts = [step['step_text'] for step in individual_steps]
                if individual_step_texts:
                    # Normalize individual steps
                    individual_normalized = [self.normalizer.normalize(text) for text in individual_step_texts]
                    # Embed individual steps
                    individual_embeddings = self.embedder.embed_batch(
                        [norm.normalized_text for norm in individual_normalized],
                        batch_size=self.config.batch_size
                    )
                    
                    # Store each individual step
                    for step_info, normalized, embedding in zip(individual_steps, individual_normalized, individual_embeddings):
                        individual_step = IndividualBDDStep(
                            id=None,
                            feature_step_id=bdd_step_id,
                            step_type=step_info['step_type'],
                            step_text=step_info['step_text'],
                            step_text_normalized=normalized.normalized_text,
                            step_index=step_info['step_index'],
                            embedding=embedding,
                            usage_count=0
                        )
                        self.db.insert_individual_bdd_step(individual_step)
                
                # Step 2: Chunk manual steps and link to BDD step
                chunks = self.chunker.chunk(manual_steps, testcase_id, self.normalizer)
                
                if chunks:
                    normalized_texts = [chunk.normalized_chunk for chunk in chunks]
                    embeddings = self.embedder.embed_batch(normalized_texts, batch_size=self.config.batch_size)
                    
                    for chunk, embedding in zip(chunks, embeddings):
                        chunk_obj = TestStepChunk(
                            chunk_id=chunk.chunk_id,
                            parent_testcase_id=chunk.parent_testcase_id,
                            original_chunk=chunk.original_chunk,
                            normalized_chunk=chunk.normalized_chunk,
                            action_verb=chunk.action_verb,
                            primary_object=chunk.primary_object,
                            placeholders=chunk.placeholders,
                            embedding=embedding,
                            cluster_id=None,
                            chunk_index=chunk.chunk_index,
                            normalization_version=self.config.normalization_version
                        )
                        
                        # Insert chunk and link to BDD step
                        chunk_db_id = self.db.insert_chunk(chunk_obj)
                        self.db.update_chunk_bdd_step(chunk_db_id, bdd_step_id)
                        chunk_count += 1
                
                pbar.set_postfix({
                    'BDD': bdd_count,
                    'chunks': chunk_count
                })
        
        print(f"\n{'='*60}")
        print(f"INGESTION SUMMARY")
        print(f"{'='*60}")
        print(f"  BDD Steps created: {bdd_count}")
        print(f"  Manual Step chunks: {chunk_count}")
        print(f"  Skipped (no BDD): {skipped_no_bdd}")
        print(f"{'='*60}\n")
        
        return bdd_count, chunk_count
    
    def ingest_csv(self, csv_path: str, testcase_id_col: str = "ID", 
                   steps_col: str = "Manual Steps", bdd_col: str = "BDD Steps"):
        """
        Legacy ingestion - redirect to new method.
        """
        return self.ingest_csv_with_bdd(csv_path, testcase_id_col, steps_col, bdd_col)
    
    def ingest_json(self, json_path: str):
        """Ingest test steps from JSON file."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        chunks_to_insert = []
        
        for item in data:
            testcase_id = item.get('testcase_id', '')
            step_text = item.get('step_text', '')
            bdd_step = item.get('bdd_step', '')
            
            if not step_text or not testcase_id:
                continue
            
            # If BDD step provided, store it
            bdd_step_id = None
            if bdd_step:
                parsed_bdd = self.bdd_parser.parse(bdd_step)
                bdd_searchable = self.bdd_parser.get_searchable_text(parsed_bdd)
                bdd_normalized = self.normalizer.normalize(bdd_searchable)
                bdd_embedding = self.embedder.embed(bdd_normalized.normalized_text)
                
                feature_step = FeatureStep(
                    id=None,
                    testcase_id=testcase_id,
                    bdd_step=bdd_step,
                    bdd_step_normalized=bdd_normalized.normalized_text,
                    scenario_name=parsed_bdd.scenario_name,
                    given_steps=parsed_bdd.given_steps,
                    when_steps=parsed_bdd.when_steps,
                    then_steps=parsed_bdd.then_steps,
                    embedding=bdd_embedding,
                    usage_count=0
                )
                bdd_step_id = self.db.insert_feature_step(feature_step)
            
            # Chunk and store manual steps
            chunks = self.chunker.chunk(step_text, testcase_id, self.normalizer)
            normalized_texts = [chunk.normalized_chunk for chunk in chunks]
            embeddings = self.embedder.embed_batch(normalized_texts, batch_size=self.config.batch_size)
            
            for chunk, embedding in zip(chunks, embeddings):
                chunk_obj = TestStepChunk(
                    chunk_id=chunk.chunk_id,
                    parent_testcase_id=chunk.parent_testcase_id,
                    original_chunk=chunk.original_chunk,
                    normalized_chunk=chunk.normalized_chunk,
                    action_verb=chunk.action_verb,
                    primary_object=chunk.primary_object,
                    placeholders=chunk.placeholders,
                    embedding=embedding,
                    cluster_id=None,
                    chunk_index=chunk.chunk_index,
                    normalization_version=self.config.normalization_version
                )
                
                chunk_db_id = self.db.insert_chunk(chunk_obj)
                if bdd_step_id:
                    self.db.update_chunk_bdd_step(chunk_db_id, bdd_step_id)
    
    def cluster_and_create_templates(self, clustering_module):
        """
        DEPRECATED: No longer needed since we link manual steps directly to BDD steps.
        Kept for backwards compatibility.
        """
        print("Note: Clustering is no longer needed - Manual Steps are now directly linked to BDD Steps.")
        print("Skipping clustering step.")
