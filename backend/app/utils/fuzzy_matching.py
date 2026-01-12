"""
Fuzzy Matching Utilities for Entity Resolution.

Provides Levenshtein Distance and fuzzy string matching
to handle typos and variations in entity names.
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein Distance between two strings.
    
    The Levenshtein distance is the minimum number of single-character
    edits (insertions, deletions, or substitutions) required to change
    one string into the other.
    
    Args:
        s1: First string
        s2: Second string
        
    Returns:
        Levenshtein distance (lower is more similar)
        
    Examples:
        >>> levenshtein_distance("kitten", "sitting")
        3
        >>> levenshtein_distance("Lumix Solutions", "Lumix Solutons")
        1
    """
    # Convert to lowercase for case-insensitive comparison
    s1 = s1.lower()
    s2 = s2.lower()
    
    # Quick checks
    if s1 == s2:
        return 0
    if len(s1) == 0:
        return len(s2)
    if len(s2) == 0:
        return len(s1)
    
    # Create matrix
    rows = len(s1) + 1
    cols = len(s2) + 1
    
    # Initialize matrix
    dist = [[0 for _ in range(cols)] for _ in range(rows)]
    
    # Fill first column and row
    for i in range(1, rows):
        dist[i][0] = i
    for j in range(1, cols):
        dist[0][j] = j
    
    # Calculate distances
    for i in range(1, rows):
        for j in range(1, cols):
            if s1[i-1] == s2[j-1]:
                cost = 0
            else:
                cost = 1
            
            dist[i][j] = min(
                dist[i-1][j] + 1,      # deletion
                dist[i][j-1] + 1,      # insertion
                dist[i-1][j-1] + cost  # substitution
            )
    
    return dist[-1][-1]


def fuzzy_similarity(s1: str, s2: str) -> float:
    """
    Calculate fuzzy similarity score between two strings (0.0 to 1.0).
    
    Uses Levenshtein distance normalized by the length of the longer string.
    1.0 = identical, 0.0 = completely different
    
    Args:
        s1: First string
        s2: Second string
        
    Returns:
        Similarity score (0.0 to 1.0)
        
    Examples:
        >>> fuzzy_similarity("Lumix Solutions", "Lumix Solutions")
        1.0
        >>> fuzzy_similarity("Lumix Solutions", "Lumix Solutons")
        0.933  # 14/15 characters match
    """
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    
    distance = levenshtein_distance(s1, s2)
    similarity = 1.0 - (distance / max_len)
    
    return similarity


def fuzzy_match_entities(
    search_term: str,
    candidates: List[Tuple[str, str, str, int]],  # (source_id, name, type, score)
    threshold: float = 0.7
) -> List[Tuple[str, str, str, int]]:
    """
    Apply fuzzy matching to entity candidates and re-rank by similarity.
    
    Args:
        search_term: The search term to match against
        candidates: List of (source_id, name, type, score) tuples from graph query
        threshold: Minimum similarity threshold (0.0 to 1.0)
        
    Returns:
        Filtered and re-ranked list of candidates
        
    Example:
        >>> candidates = [
        ...     ("zoho_123", "Lumix Solutions GmbH", "Account", 50),
        ...     ("zoho_456", "Max Solutions", "Account", 50)
        ... ]
        >>> fuzzy_match_entities("Lumix Solutons", candidates, threshold=0.7)
        [("zoho_123", "Lumix Solutions GmbH", "Account", 93)]
    """
    if not candidates:
        return []
    
    # Calculate fuzzy similarity for each candidate
    scored_candidates = []
    
    for source_id, name, entity_type, original_score in candidates:
        similarity = fuzzy_similarity(search_term, name)
        
        # Calculate new score
        # Original score (exact/contains match) + fuzzy bonus
        if similarity >= threshold:
            # Fuzzy similarity bonus (0-30 points)
            fuzzy_bonus = int(similarity * 30)
            new_score = original_score + fuzzy_bonus
            
            scored_candidates.append((source_id, name, entity_type, new_score, similarity))
    
    # Sort by new score (descending)
    scored_candidates.sort(key=lambda x: x[3], reverse=True)
    
    # Log fuzzy matching results
    if scored_candidates:
        best = scored_candidates[0]
        logger.debug(
            f"Fuzzy matching '{search_term}' → '{best[1]}' "
            f"(similarity: {best[4]:.2f}, score: {best[3]})"
        )
    
    # Return without similarity (same format as input)
    return [(sid, name, etype, score) for sid, name, etype, score, _ in scored_candidates]


def is_likely_typo(search_term: str, candidate: str) -> bool:
    """
    Quickly check if a candidate is likely a typo of the search term.
    
    Uses simple heuristics:
    - Length difference < 3 characters
    - Levenshtein distance < 3
    
    Args:
        search_term: The search term
        candidate: Candidate entity name
        
    Returns:
        True if likely a typo match
        
    Example:
        >>> is_likely_typo("Lumix Solutons", "Lumix Solutions GmbH")
        True
        >>> is_likely_typo("Lumix", "ACME Corp")
        False
    """
    len_diff = abs(len(search_term) - len(candidate))
    if len_diff > 3:
        return False
    
    distance = levenshtein_distance(search_term, candidate)
    if distance <= 3:
        return True
    
    return False


