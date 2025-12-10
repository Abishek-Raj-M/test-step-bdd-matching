"""Placeholder mapping module."""
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import spacy


@dataclass
class PlaceholderMatch:
    """Placeholder match result."""
    placeholder_map: Dict[str, str]
    placeholder_match_score: float
    missing_placeholders: List[str]


class PlaceholderMapper:
    """Maps query values to template placeholders."""
    
    def __init__(self, use_ner: bool = True):
        self.use_ner = use_ner
        self.nlp = None
        
        if use_ner:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("Warning: spaCy model not found. NER disabled.")
                self.use_ner = False
    
    def map_placeholders(self, query_text: str, query_normalized: str, 
                        template_text: str, template_normalized: str) -> PlaceholderMatch:
        """
        Map query values to template placeholders.
        
        Args:
            query_text: Original query text
            query_normalized: Normalized query text
            template_text: Original template text
            template_normalized: Normalized template text
        
        Returns:
            PlaceholderMatch with mapping results
        """
        # Detect placeholders in template
        template_placeholders = self._detect_template_placeholders(template_normalized)
        
        # Detect values in query
        query_values = self._detect_query_values(query_text, query_normalized)
        
        # Align values to placeholders
        placeholder_map = {}
        for placeholder_type in template_placeholders:
            if placeholder_type in query_values and query_values[placeholder_type]:
                # Take first value of matching type
                placeholder_map[placeholder_type] = query_values[placeholder_type][0]
        
        # Compute match score
        total_placeholders = len(template_placeholders)
        filled_placeholders = len(placeholder_map)
        placeholder_match_score = filled_placeholders / total_placeholders if total_placeholders > 0 else 1.0
        
        # Find missing placeholders
        missing_placeholders = [ph for ph in template_placeholders if ph not in placeholder_map]
        
        return PlaceholderMatch(
            placeholder_map=placeholder_map,
            placeholder_match_score=placeholder_match_score,
            missing_placeholders=missing_placeholders
        )
    
    def _detect_template_placeholders(self, template_text: str) -> List[str]:
        """Detect placeholder types in template."""
        placeholder_pattern = r'<(\w+)>'
        placeholders = re.findall(placeholder_pattern, template_text)
        return list(set(placeholders))  # Remove duplicates
    
    def _detect_query_values(self, query_text: str, query_normalized: str) -> Dict[str, List[str]]:
        """Detect values in query that could fill placeholders."""
        values: Dict[str, List[str]] = defaultdict(list)
        
        # URL pattern
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        for match in re.finditer(url_pattern, query_text, re.IGNORECASE):
            values['URL'].append(match.group())
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.finditer(email_pattern, query_text):
            values['EMAIL'].append(match.group())
        
        # Amount pattern
        amount_pattern = r'\$?\d+\.?\d*\s*(USD|EUR|GBP|dollars?|euros?|pounds?)?'
        for match in re.finditer(amount_pattern, query_text, re.IGNORECASE):
            values['AMOUNT'].append(match.group())
        
        # Date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        ]
        for pattern in date_patterns:
            for match in re.finditer(pattern, query_text, re.IGNORECASE):
                values['DATE'].append(match.group())
        
        # Number pattern (standalone)
        number_pattern = r'\b\d+(\.\d+)?\b'
        for match in re.finditer(number_pattern, query_text):
            # Skip if part of amount or date
            skip = False
            for amount in values['AMOUNT']:
                if match.group() in amount:
                    skip = True
                    break
            if skip:
                continue
            for date in values['DATE']:
                if match.group() in date:
                    skip = True
                    break
            if not skip:
                values['NUMBER'].append(match.group())
        
        # Use NER for named entities if available
        if self.use_ner and self.nlp:
            doc = self.nlp(query_text)
            for ent in doc.ents:
                if ent.label_ == 'PERSON':
                    values['PERSON'].append(ent.text)
                elif ent.label_ == 'ORG':
                    values['ORGANIZATION'].append(ent.text)
                elif ent.label_ == 'GPE' or ent.label_ == 'LOC':
                    values['LOCATION'].append(ent.text)
        
        # Extract button/field names (common in test steps)
        # Look for capitalized words or quoted strings
        button_pattern = r'["\']([^"\']+)["\']|(?:click|select|press)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        for match in re.finditer(button_pattern, query_text, re.IGNORECASE):
            if match.group(1):
                values['BUTTON'].append(match.group(1))
            elif match.group(2):
                values['BUTTON'].append(match.group(2))
        
        return values

