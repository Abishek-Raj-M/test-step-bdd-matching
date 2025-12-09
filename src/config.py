"""Configuration loader and validator."""
import yaml
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class EmbeddingConfig:
    """Embedding model configuration."""
    model_name: str
    legacy_model_name: str
    use_legacy: bool
    dim: int
    cache_dir: str


@dataclass
class RerankerConfig:
    """Reranker model configuration."""
    model_name: str
    fallback_model_name: str
    use_fallback: bool
    enabled: bool
    top_k: int


@dataclass
class ThresholdsConfig:
    """Confidence threshold configuration."""
    high_conf: float
    med_conf: float
    low_conf: float


@dataclass
class RetrievalConfig:
    """Retrieval configuration."""
    prefilter_limit: int
    relaxed_limit: int
    ef_search: int
    ef_relaxed: int


@dataclass
class ClusteringConfig:
    """Clustering configuration."""
    method: str
    threshold: float
    min_cluster_size: int


@dataclass
class FallbackConfig:
    """Fallback configuration."""
    enable_rule_synthesis: bool
    enable_llm_synthesis: bool
    enable_context_expansion: bool
    enable_lexical_search: bool


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str
    port: int
    database: str
    user: str
    password: str
    table_suffix: str = ""


@dataclass
class Config:
    """Main configuration class."""
    embedding: EmbeddingConfig
    reranker: RerankerConfig
    thresholds: ThresholdsConfig
    retrieval: RetrievalConfig
    clustering: ClusteringConfig
    fallbacks: FallbackConfig
    database: DatabaseConfig
    batch_size: int
    normalization_version: str
    fine_tuning: Dict[str, Any]
    top_k_results: int
    min_score_threshold: float


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    return Config(
        embedding=EmbeddingConfig(
            model_name=config_dict['embedding_model_name'],
            legacy_model_name=config_dict.get('embedding_model_name_legacy', config_dict['embedding_model_name']),
            use_legacy=config_dict.get('use_legacy_embedding', False),
            dim=config_dict['embedding_dim'],
            cache_dir=config_dict.get('embedding_cache_dir', ".embedding_cache")
        ),
        reranker=RerankerConfig(
            model_name=config_dict['reranker_model_name'],
            fallback_model_name=config_dict.get('reranker_model_fallback_name', config_dict['reranker_model_name']),
            use_fallback=config_dict.get('reranker_use_fallback', False),
            enabled=config_dict['reranker_enabled'],
            top_k=config_dict['reranker_top_k']
        ),
        thresholds=ThresholdsConfig(
            high_conf=config_dict.get('high_conf_threshold', 0.85),  # Optional, kept for backward compatibility
            med_conf=config_dict.get('med_conf_threshold', 0.70),
            low_conf=config_dict.get('low_conf_threshold', 0.50)
        ),
        retrieval=RetrievalConfig(
            prefilter_limit=config_dict['prefilter_limit'],
            relaxed_limit=config_dict['relaxed_limit'],
            ef_search=config_dict['ef_search'],
            ef_relaxed=config_dict['ef_relaxed']
        ),
        clustering=ClusteringConfig(
            method=config_dict['clustering_method'],
            threshold=config_dict['clustering_threshold'],
            min_cluster_size=config_dict['min_cluster_size']
        ),
        fallbacks=FallbackConfig(
            enable_rule_synthesis=config_dict['fallbacks']['enable_rule_synthesis'],
            enable_llm_synthesis=config_dict['fallbacks']['enable_llm_synthesis'],
            enable_context_expansion=config_dict['fallbacks']['enable_context_expansion'],
            enable_lexical_search=config_dict['fallbacks']['enable_lexical_search']
        ),
        database=DatabaseConfig(
            host=config_dict['database']['host'],
            port=config_dict['database']['port'],
            database=config_dict['database']['database'],
            user=config_dict['database']['user'],
            password=config_dict['database']['password'],
            table_suffix=config_dict['database'].get('table_suffix', '')
        ),
        batch_size=config_dict['batch_size'],
        normalization_version=config_dict['normalization_version'],
        fine_tuning=config_dict['fine_tuning'],
        top_k_results=config_dict.get('top_k_results', 5),
        min_score_threshold=config_dict.get('min_score_threshold', 0.0)
    )



