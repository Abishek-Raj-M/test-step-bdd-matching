"""Normalization module for test steps."""
import re
import unicodedata
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import spacy


@dataclass
class Placeholder:
    """Placeholder metadata."""
    type: str
    value: str
    position: int


@dataclass
class NormalizedResult:
    """Normalization result."""
    normalized_text: str
    placeholders: List[Placeholder]
    action_verb: Optional[str]
    primary_object: Optional[str]
    normalization_version: str
    action_canonical: Optional[str] = None
    domain_terms: List[str] = field(default_factory=list)
    count_phrases: List[str] = field(default_factory=list)


class Normalizer:
    """Normalizes test steps for consistent matching."""
    
    def __init__(self, normalization_version: str = "2.0", use_lemmatization: bool = False):
        self.normalization_version = normalization_version
        self.use_lemmatization = use_lemmatization
        self.nlp = None
        
        # Domain tokens we want to preserve verbatim (avoid lower-casing away meaning)
        self.domain_tokens = [
            "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
            "ENTER", "TAB", "SPACE", "BACKSPACE", "ESC", "ESCAPE", "CTRL", "ALT", "SHIFT", "CMD",
            "PAGEUP", "PAGEDOWN", "HOME", "END",
            "ARROWUP", "ARROWDOWN", "ARROWLEFT", "ARROWRIGHT",
            "UP ARROW", "DOWN ARROW", "LEFT ARROW", "RIGHT ARROW",
            "GREEN ARROW", "PURPLE ARROW", "RED ARROW"
        ]
        
        # Action canonicalization map
        self.action_canon_map = {
            "press": "press", "click": "press", "hit": "press", "tap": "press", "confirm": "press",
            "enter": "enter", "type": "enter", "input": "enter", "key": "enter",
            "select": "select", "choose": "select", "pick": "select",
            "navigate": "navigate", "go": "navigate", "open": "navigate",
            "verify": "verify", "check": "verify", "assert": "verify",
        }
        
        if use_lemmatization:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("Warning: spaCy model not found. Lemmatization disabled.")
                self.use_lemmatization = False
    
    def normalize(self, text: str) -> NormalizedResult:
        """Normalize a test step."""
        if not text or not text.strip():
            return NormalizedResult(
                normalized_text="",
                placeholders=[],
                action_verb=None,
                primary_object=None,
                normalization_version=self.normalization_version
            )
        
        # Step 1: Unicode normalization
        normalized = unicodedata.normalize('NFKC', text)
        
        # Step 2: Remove step numbers FIRST (before placeholder extraction)
        # This prevents "2." from becoming <AMOUNT>
        normalized = self._remove_step_numbers(normalized)
        
        # Step 3: Placeholder extraction (before case normalization to preserve case in values)
        placeholders = []
        normalized, placeholders = self._extract_placeholders(normalized, placeholders)
        
        # Step 4: Extract domain terms and counts before lowercasing
        domain_terms = self._extract_domain_terms(normalized)
        count_phrases = self._extract_count_phrases(normalized)
        
        # Step 5: Case normalization (lowercase, we'll restore domain tokens later)
        normalized = normalized.lower()
        
        # Step 6: Text cleaning
        normalized = self._clean_text(normalized)
        
        # Step 7: Optional lemmatization
        if self.use_lemmatization and self.nlp:
            normalized = self._lemmatize(normalized)
        
        # Extract action verb and primary object (on cleaned, lowercased text)
        action_verb, primary_object = self._extract_action_and_object(normalized)
        action_canonical = self._canonicalize_action(action_verb)
        
        # Re-inject canonical action token for reranker visibility
        if action_canonical and action_canonical not in normalized:
            normalized = f"{action_canonical} {normalized}".strip()
        
        # Restore domain tokens in uppercase form for visibility
        for term in domain_terms:
            normalized = self._restore_token_case(normalized, term)
        
        return NormalizedResult(
            normalized_text=normalized,
            placeholders=placeholders,
            action_verb=action_verb,
            primary_object=primary_object,
            normalization_version=self.normalization_version,
            action_canonical=action_canonical,
            domain_terms=domain_terms,
            count_phrases=count_phrases
        )
    
    def _remove_step_numbers(self, text: str) -> str:
        """Remove step numbers like '1.', '2.', '1)', 'a)', 'Step 1:' from the beginning."""
        # Remove leading step numbers at start of text or after newlines
        # Patterns: "1.", "2.", "1)", "a)", "Step 1:", "Step 1.", etc.
        patterns = [
            r'^\s*\d+\s*[\.\):\-]\s*',           # "1.", "2)", "3:", "4-" at start
            r'^\s*[a-zA-Z]\s*[\.\):\-]\s*',      # "a.", "b)", "A:" at start
            r'^\s*[Ss]tep\s*\d+\s*[\.\):\-]?\s*', # "Step 1.", "step 2:" at start
            r'\n\s*\d+\s*[\.\):\-]\s*',          # Same patterns after newlines
            r'\n\s*[a-zA-Z]\s*[\.\):\-]\s*',
            r'\n\s*[Ss]tep\s*\d+\s*[\.\):\-]?\s*',
        ]
        
        result = text
        for pattern in patterns:
            result = re.sub(pattern, '\n' if '\n' in pattern else '', result)
        
        return result.strip()
    
    def _extract_placeholders(self, text: str, placeholders: List[Placeholder]) -> tuple[str, List[Placeholder]]:
        """Extract placeholders and replace with tags."""
        result = text
        offset = 0
        
        # URL pattern
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        for match in re.finditer(url_pattern, text, re.IGNORECASE):
            placeholder = Placeholder(
                type="URL",
                value=match.group(),
                position=match.start() - offset
            )
            placeholders.append(placeholder)
            result = result[:match.start() - offset] + "<URL>" + result[match.end() - offset:]
            offset += len(match.group()) - 5  # 5 = len("<URL>")
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.finditer(email_pattern, text):
            placeholder = Placeholder(
                type="EMAIL",
                value=match.group(),
                position=match.start() - offset
            )
            placeholders.append(placeholder)
            result = result[:match.start() - offset] + "<EMAIL>" + result[match.end() - offset:]
            offset += len(match.group()) - 7  # 7 = len("<EMAIL>")
        
        # Amount pattern - MUST have currency indicator
        # Matches: $100, $100.50, 100 USD, 100.50 EUR, £50, €50
        amount_patterns = [
            r'[\$£€]\s*\d+(?:\.\d{1,2})?',  # $100, $100.50, £50, €50
            r'\d+(?:\.\d{1,2})?\s*(?:USD|EUR|GBP|dollars?|euros?|pounds?)\b',  # 100 USD, 100.50 EUR
        ]
        for amount_pattern in amount_patterns:
            for match in re.finditer(amount_pattern, result, re.IGNORECASE):
                placeholder = Placeholder(
                    type="AMOUNT",
                    value=match.group(),
                    position=match.start()
                )
                placeholders.append(placeholder)
                result = result[:match.start()] + "<AMOUNT>" + result[match.end():]
        
        # Date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # 2024-01-15
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',  # Jan 15, 2024
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'  # 01/15/2024
        ]
        for pattern in date_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                placeholder = Placeholder(
                    type="DATE",
                    value=match.group(),
                    position=match.start() - offset
                )
                placeholders.append(placeholder)
                result = result[:match.start() - offset] + "<DATE>" + result[match.end() - offset:]
                offset += len(match.group()) - 6  # 6 = len("<DATE>")
        
        # Number pattern (standalone numbers, not part of amounts/dates/counts/domain tokens)
        number_pattern = r'\b\d+(\.\d+)?\b'
        for match in re.finditer(number_pattern, text):
            # Skip if already part of a placeholder
            skip = False
            for ph in placeholders:
                if ph.position <= match.start() <= ph.position + len(ph.value):
                    skip = True
                    break
            if skip:
                continue
            
            # Skip counts like "4 times" or "4x"
            following = text[match.end():match.end() + 6].lower()
            if re.match(r'\s*(times|x)\b', following):
                continue
            
            # Skip F-key patterns (e.g., F8) and arrow counts already captured as domain terms
            span_start = max(match.start() - 1, 0)
            if re.match(r'F\d{1,2}', text[span_start:match.end()+1], re.IGNORECASE):
                continue
            
            placeholder = Placeholder(
                type="NUMBER",
                value=match.group(),
                position=match.start() - offset
            )
            placeholders.append(placeholder)
            result = result[:match.start() - offset] + "<NUMBER>" + result[match.end() - offset:]
            offset += len(match.group()) - 8  # 8 = len("<NUMBER>")
        
        return result, placeholders
    
    def _clean_text(self, text: str) -> str:
        """Clean text by removing artifacts."""
        # Remove list numbering
        text = re.sub(r'^\d+\.\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[a-z]\)\s*', '', text, flags=re.MULTILINE | re.IGNORECASE)
        
        # Remove bullets
        text = re.sub(r'[•\-\*]\s*', ' ', text)
        
        # Remove artifacts and special characters (keep essential punctuation)
        text = re.sub(r'[^\w\s<>.,;:!?()\-\']', ' ', text)
        
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Strip trailing punctuation (except if part of placeholder)
        text = text.strip('.,;:!?')
        
        return text.strip()
    
    def _lemmatize(self, text: str) -> str:
        """Lemmatize text using spaCy."""
        if not self.nlp:
            return text
        
        doc = self.nlp(text)
        lemmatized = []
        for token in doc:
            if token.pos_ in ['VERB', 'NOUN']:
                lemmatized.append(token.lemma_)
            else:
                lemmatized.append(token.text)
        return ' '.join(lemmatized)
    
    def _canonicalize_action(self, action_verb: Optional[str]) -> Optional[str]:
        """Map action verb to canonical form."""
        if not action_verb:
            return None
        return self.action_canon_map.get(action_verb, action_verb)
    
    def _extract_action_and_object(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Extract action verb and primary object from normalized text."""
        if not self.nlp:
            # Simple regex-based extraction
            action_verbs = ['click', 'select', 'navigate', 'verify', 'check', 'enter', 'input', 
                           'submit', 'press', 'open', 'close', 'create', 'delete', 'update',
                           'grab', 'mark', 'strike', 'scan', 'switch', 'add', 'remove']
            
            words = text.split()
            action_verb = None
            for word in words:
                if word in action_verbs:
                    action_verb = word
                    break
            
            # Primary object is typically the noun after the verb
            primary_object = None
            if action_verb:
                idx = words.index(action_verb) if action_verb in words else -1
                if idx >= 0 and idx + 1 < len(words):
                    # Skip common words
                    skip_words = ['the', 'a', 'an', 'to', 'on', 'in', 'at', 'for', 'with']
                    for i in range(idx + 1, len(words)):
                        if words[i] not in skip_words and not words[i].startswith('<'):
                            primary_object = words[i]
                            break
            
            return action_verb, primary_object
        
        # Use spaCy for better extraction
        doc = self.nlp(text)
        action_verb = None
        primary_object = None
        
        for token in doc:
            if token.pos_ == 'VERB' and not action_verb:
                action_verb = token.lemma_
            elif token.pos_ == 'NOUN' and not primary_object and action_verb:
                primary_object = token.lemma_
                break
        
        return action_verb, primary_object

    def _extract_domain_terms(self, text: str) -> List[str]:
        """Extract domain tokens we want to preserve (F-keys, arrows, special keys)."""
        terms = []
        # Normalize spaces and consider uppercase for matching
        upper_text = text.upper()
        # Patterns: F-keys, arrows, keys
        patterns = [
            r'\bF(?:1[0-2]?|[1-9])\b',
            r'\bENTER\b',
            r'\bTAB\b',
            r'\bSPACE\b',
            r'\bBACKSPACE\b',
            r'\bESC(?:APE)?\b',
            r'\bCTRL\b',
            r'\bALT\b',
            r'\bSHIFT\b',
            r'\bCMD\b',
            r'\bPAGEUP\b',
            r'\bPAGEDOWN\b',
            r'\bHOME\b',
            r'\bEND\b',
            r'\b(?:UP|DOWN|LEFT|RIGHT)\s+ARROW\b',
            r'\bARROW(?:UP|DOWN|LEFT|RIGHT)\b',
            r'\b(?:GREEN|PURPLE|RED)\s+ARROW\b'
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, upper_text, re.IGNORECASE):
                term = match.group(0).strip()
                if term not in terms:
                    terms.append(term)
        return terms

    def _restore_token_case(self, text: str, token: str) -> str:
        """Restore a token to uppercase within the text."""
        pattern = re.compile(r'\b' + re.escape(token.lower()) + r'\b', re.IGNORECASE)
        return pattern.sub(token.upper(), text)

    def _extract_count_phrases(self, text: str) -> List[str]:
        """Extract count phrases like '4 times' or '3x'."""
        phrases = []
        for match in re.finditer(r'\b\d+\s*(?:times|x)\b', text, re.IGNORECASE):
            phrases.append(match.group(0))
        return phrases


