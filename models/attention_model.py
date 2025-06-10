import torch
import torch.nn as nn
import math
from typing import Optional, Tuple

class MultiHeadAttention(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.num_heads = config.num_attention_heads
        self.hidden_size = config.hidden_size
        self.head_size = self.hidden_size // self.num_heads
        
        self.query = nn.Linear(config.hidden_size, config.hidden_size)
        self.key = nn.Linear(config.hidden_size, config.hidden_size)
        self.value = nn.Linear(config.hidden_size, config.hidden_size)
        self.proj = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.dropout)
        
    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_size = hidden_states.size(0)
        
        # Linear projections and reshape
        query = self.query(hidden_states)
        key = self.key(hidden_states)
        value = self.value(hidden_states)
        
        # Reshape to (batch, num_heads, seq_len, head_size)
        query = query.view(batch_size, -1, self.num_heads, self.head_size).transpose(1, 2)
        key = key.view(batch_size, -1, self.num_heads, self.head_size).transpose(1, 2)
        value = value.view(batch_size, -1, self.num_heads, self.head_size).transpose(1, 2)
        
        # Scaled dot-product attention
        scale = math.sqrt(self.head_size)
        scores = torch.matmul(query, key.transpose(-2, -1)) / scale
        
        if attention_mask is not None:
            scores = scores + attention_mask
            
        attn_weights = torch.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        context = torch.matmul(attn_weights, value)
        
        # Reshape back
        context = context.transpose(1, 2).contiguous()
        context = context.view(batch_size, -1, self.hidden_size)
        
        # Final projection
        output = self.proj(context)
        
        return output, attn_weights

class MicrobialSignatureModel(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        # Embedding layer
        self.embeddings = nn.Embedding(config.vocab_size, config.hidden_size)
        self.position_embeddings = nn.Embedding(config.max_position_embeddings, config.hidden_size)
        
        # Attention layers
        self.attention_layers = nn.ModuleList([
            MultiHeadAttention(config) for _ in range(config.num_hidden_layers)
        ])
        
        # Feed-forward layers
        self.feed_forward = nn.Sequential(
            nn.Linear(config.hidden_size, config.intermediate_size),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.intermediate_size, config.hidden_size),
            nn.Dropout(config.dropout)
        )
        
        # Layer normalization
        self.layer_norm1 = nn.LayerNorm(config.hidden_size)
        self.layer_norm2 = nn.LayerNorm(config.hidden_size)
        
        # Output layers for different tasks
        self.has_signature_classifier = nn.Linear(config.hidden_size, 1)
        self.sequencing_type_classifier = nn.Linear(config.hidden_size, config.num_sequencing_types)
        self.body_site_classifier = nn.Linear(config.hidden_size, config.num_body_sites)
        
    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> dict:
        batch_size, seq_length = input_ids.size()
        
        # Create position IDs
        position_ids = torch.arange(seq_length, dtype=torch.long, device=input_ids.device)
        position_ids = position_ids.unsqueeze(0).expand(batch_size, -1)
        
        # Get embeddings
        embeddings = self.embeddings(input_ids)
        position_embeddings = self.position_embeddings(position_ids)
        hidden_states = embeddings + position_embeddings
        
        # Apply attention layers
        all_attentions = []
        for attention_layer in self.attention_layers:
            hidden_states = self.layer_norm1(hidden_states)
            hidden_states, attention_weights = attention_layer(hidden_states, attention_mask)
            hidden_states = self.feed_forward(hidden_states)
            hidden_states = self.layer_norm2(hidden_states)
            all_attentions.append(attention_weights)
            
        # Pool the output (use [CLS] token or mean pooling)
        pooled_output = hidden_states.mean(dim=1)
        
        # Get predictions for different tasks
        has_signature = torch.sigmoid(self.has_signature_classifier(pooled_output))
        sequencing_type = self.sequencing_type_classifier(pooled_output)
        body_site = self.body_site_classifier(pooled_output)
        
        return {
            'has_signature': has_signature,
            'sequencing_type': sequencing_type,
            'body_site': body_site,
            'hidden_states': hidden_states,
            'attentions': all_attentions
        } 