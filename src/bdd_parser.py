"""BDD Step Parser - Extracts Given/When/Then from BDD text."""
import re
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ParsedBDD:
    """Parsed BDD step components."""
    scenario_name: Optional[str]
    given_steps: Optional[str]
    when_steps: Optional[str]
    then_steps: Optional[str]
    full_text: str


class BDDParser:
    """Parses BDD/Gherkin text into components."""
    
    def parse(self, bdd_text: str) -> ParsedBDD:
        """
        Parse BDD text into Given/When/Then components.
        
        Args:
            bdd_text: Full BDD/Gherkin text
        
        Returns:
            ParsedBDD with extracted components
        """
        if not bdd_text or not bdd_text.strip():
            return ParsedBDD(
                scenario_name=None,
                given_steps=None,
                when_steps=None,
                then_steps=None,
                full_text=""
            )
        
        # Extract scenario name
        scenario_name = self._extract_scenario_name(bdd_text)
        
        # Extract Given steps
        given_steps = self._extract_section(bdd_text, 'Given')
        
        # Extract When steps
        when_steps = self._extract_section(bdd_text, 'When')
        
        # Extract Then steps
        then_steps = self._extract_section(bdd_text, 'Then')
        
        return ParsedBDD(
            scenario_name=scenario_name,
            given_steps=given_steps,
            when_steps=when_steps,
            then_steps=then_steps,
            full_text=bdd_text.strip()
        )
    
    def _extract_scenario_name(self, text: str) -> Optional[str]:
        """Extract scenario name from BDD text."""
        # Match: Scenario: Name, Scenario Outline: Name
        patterns = [
            r'Scenario(?:\s+Outline)?:\s*(.+?)(?:\n|$)',
            r'Feature:\s*(.+?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_section(self, text: str, keyword: str) -> Optional[str]:
        """Extract a section (Given/When/Then) including And/But continuations."""
        # Pattern to match the keyword and subsequent And/But lines
        # until the next keyword or end
        pattern = rf'{keyword}\s+(.+?)(?=\n\s*(?:Given|When|Then|Scenario|Feature|$)|\Z)'
        
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            section = match.group(0).strip()
            # Clean up and include And/But lines
            lines = section.split('\n')
            result_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    result_lines.append(line)
            return '\n'.join(result_lines) if result_lines else None
        
        return None
    
    def get_searchable_text(self, parsed: ParsedBDD) -> str:
        """Get searchable text from parsed BDD for embedding."""
        parts = []
        
        if parsed.scenario_name:
            parts.append(parsed.scenario_name)
        if parsed.given_steps:
            parts.append(parsed.given_steps)
        if parsed.when_steps:
            parts.append(parsed.when_steps)
        if parsed.then_steps:
            parts.append(parsed.then_steps)
        
        return ' '.join(parts) if parts else parsed.full_text
    
    def extract_individual_steps(self, bdd_text: str) -> list:
        """
        Extract individual Given/When/Then steps from BDD text.
        
        Returns:
            List of dicts with keys: step_type, step_text, step_index
        """
        individual_steps = []
        lines = bdd_text.split('\n')
        
        current_type = None
        step_index = 0
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Check for scenario/feature lines
            if re.match(r'Scenario(?:\s+Outline)?:', line, re.IGNORECASE):
                continue
            if re.match(r'Feature:', line, re.IGNORECASE):
                continue
            if re.match(r'Examples?:', line, re.IGNORECASE):
                break  # Stop at examples table
            
            # Check for Given/When/Then/And/But
            if re.match(r'Given\s+', line, re.IGNORECASE):
                current_type = 'Given'
                step_text = re.sub(r'^Given\s+', '', line, flags=re.IGNORECASE).strip()
                individual_steps.append({
                    'step_type': current_type,
                    'step_text': step_text,
                    'step_index': step_index
                })
                step_index += 1
            elif re.match(r'When\s+', line, re.IGNORECASE):
                current_type = 'When'
                step_text = re.sub(r'^When\s+', '', line, flags=re.IGNORECASE).strip()
                individual_steps.append({
                    'step_type': current_type,
                    'step_text': step_text,
                    'step_index': step_index
                })
                step_index += 1
            elif re.match(r'Then\s+', line, re.IGNORECASE):
                current_type = 'Then'
                step_text = re.sub(r'^Then\s+', '', line, flags=re.IGNORECASE).strip()
                individual_steps.append({
                    'step_type': current_type,
                    'step_text': step_text,
                    'step_index': step_index
                })
                step_index += 1
            elif re.match(r'(And|But)\s+', line, re.IGNORECASE) and current_type:
                # Continue with current type
                step_text = re.sub(r'^(And|But)\s+', '', line, flags=re.IGNORECASE).strip()
                individual_steps.append({
                    'step_type': current_type,
                    'step_text': step_text,
                    'step_index': step_index
                })
                step_index += 1
        
        return individual_steps


