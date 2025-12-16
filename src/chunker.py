"""Chunking module for splitting multi-action test steps."""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import spacy


@dataclass
class Chunk:
    """A single atomic chunk."""
    chunk_id: str
    parent_testcase_id: str
    original_chunk: str
    normalized_chunk: str
    chunk_index: int
    action_verb: Optional[str]
    primary_object: Optional[str]
    placeholders: List[Dict[str, Any]]


class Chunker:
    """Splits multi-action test steps into atomic chunks."""
    
    def __init__(self, min_tokens: int = 3, max_tokens: int = 20, use_dependency_parsing: bool = True):
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.use_dependency_parsing = use_dependency_parsing
        self.nlp = None
        
        if use_dependency_parsing:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("Warning: spaCy model not found. Using simple splitting.")
                self.use_dependency_parsing = False
    
    def chunk(self, text: str, parent_testcase_id: str, normalizer) -> List[Chunk]:
        """Split text into atomic chunks."""
        if not text or not text.strip():
            return []
        
        # Step 1: Split on delimiters
        initial_chunks = self._split_on_delimiters(text)
        
        # Step 2: Further split using dependency parsing if enabled
        if self.use_dependency_parsing and self.nlp:
            chunks = []
            for chunk_text in initial_chunks:
                chunks.extend(self._split_by_dependency(chunk_text))
        else:
            chunks = initial_chunks
        
        # Step 3: Filter noise
        chunks = self._filter_noise(chunks)
        
        # Step 4: Normalize and create Chunk objects
        result = []
        for idx, chunk_text in enumerate(chunks):
            normalized = normalizer.normalize(chunk_text)
            
            # Check token count
            token_count = len(normalized.normalized_text.split())
            if token_count > self.max_tokens:
                # Attempt further splitting
                sub_chunks = self._split_long_chunk(chunk_text, normalizer)
                for sub_idx, sub_chunk_text in enumerate(sub_chunks):
                    sub_normalized = normalizer.normalize(sub_chunk_text)
                    chunk_obj = Chunk(
                        chunk_id=f"{parent_testcase_id}_chunk_{idx}_{sub_idx}",
                        parent_testcase_id=parent_testcase_id,
                        original_chunk=sub_chunk_text,
                        normalized_chunk=sub_normalized.normalized_text,
                        chunk_index=len(result),
                        action_verb=sub_normalized.action_verb,
                        primary_object=sub_normalized.primary_object,
                        placeholders=[{"type": p.type, "value": p.value, "position": p.position} 
                                     for p in sub_normalized.placeholders]
                    )
                    result.append(chunk_obj)
            else:
                chunk_obj = Chunk(
                    chunk_id=f"{parent_testcase_id}_chunk_{idx}",
                    parent_testcase_id=parent_testcase_id,
                    original_chunk=chunk_text,
                    normalized_chunk=normalized.normalized_text,
                    chunk_index=idx,
                    action_verb=normalized.action_verb,
                    primary_object=normalized.primary_object,
                    placeholders=[{"type": p.type, "value": p.value, "position": p.position} 
                                 for p in normalized.placeholders]
                )
                result.append(chunk_obj)
        
        return result
    
    def _split_on_delimiters(self, text: str) -> List[str]:
        """Split text on common delimiters."""
        # Split on newlines
        chunks = re.split(r'\n+', text)
        
        # Further split on bullets and semicolons
        result = []
        for chunk in chunks:
            # Split on bullets
            sub_chunks = re.split(r'[•\-\*]\s*', chunk)
            for sub_chunk in sub_chunks:
                # Split on semicolons
                semicolon_chunks = re.split(r';\s*', sub_chunk)
                result.extend(semicolon_chunks)
        
        return [chunk.strip() for chunk in result if chunk.strip()]
    
    def _split_by_dependency(self, text: str) -> List[str]:
        """Split text using dependency parsing to identify multi-verb sentences."""
        if not self.nlp:
            return [text]
        
        doc = self.nlp(text)
        
        # Find all verbs
        verbs = [token for token in doc if token.pos_ == 'VERB']
        
        if len(verbs) <= 1:
            return [text]
        
        # Split on conjunctions and multiple verbs
        chunks = []
        current_chunk = []
        last_verb_idx = -1
        
        for token in doc:
            # Check if this is a new verb after a conjunction
            if token.pos_ == 'VERB' and last_verb_idx >= 0:
                # Check if there's a conjunction before this verb
                for prev_token in token.lefts:
                    if prev_token.dep_ == 'cc' or prev_token.text.lower() in ['and', 'or', 'then']:
                        # Start new chunk
                        if current_chunk:
                            chunks.append(' '.join([t.text for t in current_chunk]))
                        current_chunk = [token]
                        last_verb_idx = token.i
                        break
                else:
                    current_chunk.append(token)
            else:
                current_chunk.append(token)
                if token.pos_ == 'VERB':
                    last_verb_idx = token.i
        
        if current_chunk:
            chunks.append(' '.join([t.text for t in current_chunk]))
        
        return chunks if chunks else [text]
    
    def _filter_noise(self, chunks: List[str]) -> List[str]:
        """Filter out noise chunks."""
        result = []
        for chunk in chunks:
            # Check token count
            tokens = chunk.split()
            if len(tokens) < self.min_tokens:
                continue
            
            # Check if it has a verb (simple check)
            has_verb = any(word.lower() in [
                'click', 'select', 'navigate', 'verify', 'check', 'enter', 'input',
                'submit', 'press', 'open', 'close', 'create', 'delete', 'update',
                'grab', 'mark', 'strike', 'scan', 'switch', 'add', 'remove', 'void',
                'accept', 'locate', 'use', 'finish', 'payout', 'log', 'login'
            ] for word in tokens)
            
            if not has_verb:
                continue
            
            # Check if it's pure punctuation/whitespace
            if not re.search(r'[a-zA-Z]', chunk):
                continue
            
            result.append(chunk)
        
        return result
    
    def _split_long_chunk(self, text: str, normalizer) -> List[str]:
        """Split a chunk that exceeds max_tokens."""
        if self.use_dependency_parsing and self.nlp:
            return self._split_by_dependency(text)
        
        # Simple splitting on commas and conjunctions
        chunks = re.split(r',\s*(?:and|or|then)\s+', text)
        if len(chunks) == 1:
            chunks = re.split(r'\s+(?:and|or|then)\s+', text)
        
        return [chunk.strip() for chunk in chunks if chunk.strip()]












