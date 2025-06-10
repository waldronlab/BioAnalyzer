import torch
import tiktoken
from typing import List, Dict, Union

class AdvancedTextProcessor:
    def __init__(self, model_name: str = "gpt2"):
        self.tokenizer = tiktoken.get_encoding(model_name)
        # Add special tokens
        self.bos_token_id = 1
        self.eos_token_id = 2
        self.pad_token_id = 0
        self.sep_token_id = 3
        
    def encode_text(self, text: str) -> torch.Tensor:
        """Encode text using tiktoken for better compatibility with modern LLMs"""
        # Add BOS token at start
        tokens = [self.bos_token_id] + self.tokenizer.encode(text)
        return torch.tensor(tokens, dtype=torch.long)
    
    def decode_tokens(self, tokens: Union[torch.Tensor, List[int]]) -> str:
        """Decode tokens back to text"""
        try:
            # Convert tensor to list if needed
            if isinstance(tokens, torch.Tensor):
                if tokens.dim() > 1:  # If tensor has multiple dimensions
                    tokens = tokens.squeeze().tolist()  # Remove extra dimensions
                else:
                    tokens = tokens.tolist()
            elif isinstance(tokens, list) and isinstance(tokens[0], list):
                tokens = tokens[0]  # Take first sequence if list of lists
            
            # Ensure we have a flat list of integers
            if not isinstance(tokens, list):
                tokens = [int(tokens)]
            
            # Filter out special tokens
            tokens = [t for t in tokens if t not in [self.bos_token_id, self.eos_token_id, self.pad_token_id, self.sep_token_id]]
            
            # Convert to integers if needed
            tokens = [int(t) for t in tokens]
            
            return self.tokenizer.decode(tokens)
        except Exception as e:
            print(f"Error decoding tokens: {str(e)}")
            print(f"Token type: {type(tokens)}")
            print(f"Token content: {tokens}")
            return "Error decoding response"
    
    def batch_encode(self, texts: List[str], max_length: int = 512, pad: bool = True) -> torch.Tensor:
        """Batch encode texts with optional padding"""
        encoded = []
        for text in texts:
            # Add BOS token and encode
            tokens = [self.bos_token_id] + self.tokenizer.encode(text)
            # Truncate if needed
            if len(tokens) > max_length:
                tokens = tokens[:max_length]
            encoded.append(tokens)
        
        if pad:
            max_len = max(len(x) for x in encoded)
            encoded = [x + [self.pad_token_id] * (max_len - len(x)) for x in encoded]
        return torch.tensor(encoded, dtype=torch.long)
    
    def create_attention_mask(self, encoded_texts: torch.Tensor) -> torch.Tensor:
        """Create attention mask for padded sequences"""
        return (encoded_texts != self.pad_token_id).float()

# Additional utility functions for text preprocessing
def clean_scientific_text(text: str) -> str:
    """Clean scientific text by handling common patterns in academic papers"""
    # Add specific cleaning rules for scientific papers
    import re
    
    # Remove reference citations
    text = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', text)
    
    # Remove figure/table references
    text = re.sub(r'(Fig\.|Figure|Table)\s*\d+[A-Za-z]?', '', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text 