from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelConfig:
    """Configuration for the microbial signature model"""
    
    # Model architecture
    hidden_size: int = 768
    num_hidden_layers: int = 6
    num_attention_heads: int = 12
    intermediate_size: int = 3072
    hidden_dropout_prob: float = 0.1
    attention_probs_dropout_prob: float = 0.1
    max_position_embeddings: int = 512
    
    # Vocabulary and tokenization
    vocab_size: int = 50257  # GPT-2 vocabulary size
    pad_token_id: int = 0
    
    # Task-specific settings
    num_sequencing_types: int = 4  # Adjust based on your categories
    num_body_sites: int = 10       # Adjust based on your categories
    
    # Training settings
    batch_size: int = 32
    learning_rate: float = 5e-5
    weight_decay: float = 0.01
    warmup_steps: int = 1000
    max_steps: int = 100000
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0
    
    # Regularization
    dropout: float = 0.1
    
    # Optimization
    optimizer: str = "adamw"
    scheduler: str = "linear"
    
    # Hardware
    device: str = "cuda"  # or "cpu"
    fp16: bool = False    # Mixed precision training
    
    # Logging and checkpointing
    logging_steps: int = 100
    save_steps: int = 1000
    eval_steps: int = 1000
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        assert self.hidden_size % self.num_attention_heads == 0, \
            "Hidden size must be divisible by number of attention heads"
        assert self.max_position_embeddings <= 512, \
            "Position embeddings limited to 512 for efficiency" 