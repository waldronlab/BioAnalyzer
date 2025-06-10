import torch
import pandas as pd
import json
import logging
from pathlib import Path
from tqdm import tqdm
from typing import Dict, List, Tuple
import io
from torch.nn.utils import clip_grad_norm_

# Use absolute imports
from models.config import ModelConfig
from models.conversation_model import ConversationalBugSigModel
from utils.text_processing import AdvancedTextProcessor
from utils.data_processor import create_conversation_dataloaders

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EarlyStopping:
    def __init__(self, patience=3, min_delta=0.001):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None
        self.should_stop = False

    def __call__(self, val_loss):
        if self.best_loss is None:
            self.best_loss = val_loss
            return False

        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True

        return self.should_stop

def load_knowledge_base(filepath: str) -> pd.DataFrame:
    """Load and preprocess the BugSigDB knowledge base.
    
    Args:
        filepath: Path to the knowledge base CSV file
        
    Returns:
        Preprocessed DataFrame with BugSigDB entries
    """
    logger.info(f"Loading knowledge base from {filepath}")
    
    # First, read the raw file to get the header line
    with open(filepath, 'r') as f:
        # Skip the first two comment lines
        f.readline()  # Skip first line
        f.readline()  # Skip second line
        header_line = f.readline().strip()  # Get the header line
    
    # Split the header line into column names and make them unique
    raw_columns = header_line.split(',')
    
    # Create unique column names by adding suffixes to duplicates
    column_names = []
    seen = {}
    
    for col in raw_columns:
        if col in seen:
            seen[col] += 1
            column_names.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            column_names.append(col)
    
    # Print original and mapped column names for debugging
    logger.info("Column name mapping:")
    for orig, new in zip(raw_columns, column_names):
        logger.info(f"Original: {orig} -> New: {new}")
    
    # Read the CSV with unique column names
    df = pd.read_csv(filepath, skiprows=2, names=column_names)
    
    # Create required columns from existing data
    # Map the actual column names to our required fields based on the CSV structure
    column_mapping = {
        'pmid': 'NA',  # Using the first NA column for PMID
        'title': 'Study 11',  # Using Study name as title
        'abstract': 'Cases were identified by HIV rapid or ELISA test and subsequent Western blot following recommendations for HIV diagnosis by the Brazilian Ministry of Health.',  # Using the description field
        'body_site': 'Uterus',  # Using the body site field
        'sequencing_type': '16S'  # Using the sequencing type field
    }
    
    # Find the actual column names in our unique column names
    actual_mapping = {}
    for target, source in column_mapping.items():
        matching_cols = [col for col in column_names if col == source]
        if matching_cols:
            actual_mapping[target] = matching_cols[0]
        else:
            logger.warning(f"Could not find column matching '{source}'")
            actual_mapping[target] = None
    
    # Create the processed DataFrame with available columns
    processed_df = pd.DataFrame()
    
    if actual_mapping['pmid']:
        processed_df['pmid'] = df[actual_mapping['pmid']].fillna('NA')
    else:
        processed_df['pmid'] = 'NA'
        
    if actual_mapping['title']:
        processed_df['title'] = df[actual_mapping['title']].fillna('')
    else:
        processed_df['title'] = ''
        
    if actual_mapping['abstract']:
        processed_df['abstract'] = df[actual_mapping['abstract']].fillna('')
    else:
        processed_df['abstract'] = ''
        
    if actual_mapping['body_site']:
        processed_df['body_site'] = df[actual_mapping['body_site']].fillna('Other')
    else:
        processed_df['body_site'] = 'Other'
        
    if actual_mapping['sequencing_type']:
        processed_df['sequencing_type'] = df[actual_mapping['sequencing_type']].fillna('Other')
    else:
        processed_df['sequencing_type'] = 'Other'
    
    # Filter out rows with NA PMIDs
    processed_df = processed_df[processed_df['pmid'] != 'NA'].copy()
    
    # Ensure we have at least some valid entries
    if len(processed_df) == 0:
        raise ValueError("No valid entries found in knowledge base after processing")
    
    logger.info(f"Processed {len(processed_df)} entries from knowledge base")
    return processed_df

def load_conversation_data(filepath: str) -> Tuple[List[Dict], List[Dict]]:
    """Load and split conversation training data.
    
    Args:
        filepath: Path to the conversation JSON file
        
    Returns:
        Tuple of (training conversations, validation conversations)
    """
    logger.info(f"Loading conversation data from {filepath}")
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if not isinstance(data, dict) or 'conversations' not in data:
            raise ValueError("Invalid conversation data format. Expected {'conversations': [...]} structure")
            
        conversations = data['conversations']
        if not conversations:
            raise ValueError("No conversations found in the data")
            
        # Validate conversation format
        for i, conv in enumerate(conversations):
            if not isinstance(conv, dict):
                raise ValueError(f"Conversation {i} is not a dictionary")
            if 'query' not in conv:
                raise ValueError(f"Conversation {i} missing 'query' field")
            if 'response' not in conv:
                raise ValueError(f"Conversation {i} missing 'response' field")
        
        # Log sample conversation for debugging
        if conversations:
            logger.info("Sample conversation format:")
            logger.info(json.dumps(conversations[0], indent=2))
        
        # Split into train and validation (90/10)
        train_size = int(0.9 * len(conversations))
        if train_size == 0:
            raise ValueError("Not enough conversations for training split")
            
        train_data = conversations[:train_size]
        val_data = conversations[train_size:]
        
        logger.info(f"Split {len(conversations)} conversations into {len(train_data)} training and {len(val_data)} validation samples")
        
        return train_data, val_data
        
    except FileNotFoundError:
        logger.error(f"Conversation data file not found: {filepath}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in conversation data: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error loading conversation data: {str(e)}")
        raise

def train_conversation_model(
    knowledge_base_path: str,
    conversation_data_path: str,
    output_dir: str,
    config: ModelConfig = None,
    num_epochs: int = 10,
    patience: int = 3
):
    """Train the conversational model with improved training loop.
    
    Args:
        knowledge_base_path: Path to BugSigDB knowledge base
        conversation_data_path: Path to conversation training data
        output_dir: Directory to save model checkpoints
        config: Model configuration (optional)
        num_epochs: Number of training epochs
        patience: Number of epochs to wait for improvement before early stopping
    """
    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load data
    knowledge_base = load_knowledge_base(knowledge_base_path)
    train_conversations, val_conversations = load_conversation_data(conversation_data_path)
    
    # Log data sizes
    logger.info(f"Knowledge base size: {len(knowledge_base)} entries")
    logger.info(f"Training conversations: {len(train_conversations)}")
    logger.info(f"Validation conversations: {len(val_conversations)}")
    
    # Create or update config
    if config is None:
        config = ModelConfig(
            knowledge_base_size=len(knowledge_base),
            vocab_size=50257,  # GPT-2 vocabulary size
            hidden_size=1024,
            num_hidden_layers=8,
            num_attention_heads=16,
            max_position_embeddings=512,
            device="cpu"  # Force CPU usage for stability
        )
    
    # Initialize model and move to device
    logger.info("Initializing model...")
    model = ConversationalBugSigModel(config)
    device = torch.device("cpu")  # Force CPU
    model = model.to(device)
    
    # Create dataloaders with proper attention masking
    logger.info("Creating dataloaders...")
    train_dataloader, val_dataloader = create_conversation_dataloaders(
        train_conversations=train_conversations,
        eval_conversations=val_conversations,
        knowledge_base=knowledge_base,
        batch_size=config.batch_size
    )
    
    # Log dataloader sizes
    logger.info(f"Number of training batches: {len(train_dataloader)}")
    logger.info(f"Number of validation batches: {len(val_dataloader)}")
    
    # Setup optimizer with weight decay
    no_decay = ['bias', 'LayerNorm.weight']
    optimizer_grouped_parameters = [
        {
            'params': [p for n, p in model.named_parameters() 
                      if not any(nd in n for nd in no_decay)],
            'weight_decay': config.weight_decay
        },
        {
            'params': [p for n, p in model.named_parameters() 
                      if any(nd in n for nd in no_decay)],
            'weight_decay': 0.0
        }
    ]
    
    optimizer = torch.optim.AdamW(
        optimizer_grouped_parameters,
        lr=config.learning_rate
    )
    
    # Setup learning rate scheduler with safety check
    total_steps = len(train_dataloader) * num_epochs
    if total_steps == 0:
        logger.error("No training steps available. Check if the training data is empty or batch size is too large.")
        return None
        
    logger.info(f"Total training steps: {total_steps}")
    
    # Use a simpler scheduler for small datasets
    if total_steps < 100:  # Arbitrary threshold for small datasets
        logger.info("Small dataset detected, using StepLR scheduler instead of OneCycleLR")
        scheduler = torch.optim.lr_scheduler.StepLR(
            optimizer,
            step_size=max(1, num_epochs // 3),  # Step every third of total epochs
            gamma=0.1  # Reduce LR by factor of 10
        )
    else:
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=config.learning_rate,
            total_steps=total_steps,
            pct_start=0.1  # 10% warmup
        )
    
    # Initialize early stopping
    early_stopping = EarlyStopping(patience=patience)
    
    # Training loop
    logger.info("Starting training...")
    best_val_loss = float('inf')
    grad_norm = 0.0
    
    for epoch in range(num_epochs):
        # Training
        model.train()
        total_train_loss = 0
        train_steps = 0
        
        progress_bar = tqdm(train_dataloader, desc=f"Epoch {epoch + 1}/{num_epochs}")
        for batch in progress_bar:
            # Move batch to device and ensure proper attention masks
            batch = {k: v.to(device) for k, v in batch.items()}
            attention_mask = (batch['query_ids'] != config.pad_token_id)
            
            # Forward pass with attention mask
            outputs = model(
                query_ids=batch['query_ids'],
                context_ids=batch['context_ids'],
                knowledge_ids=batch['knowledge_ids'],
                response_ids=batch['response_ids'],
                query_mask=attention_mask,
                context_mask=(batch['context_ids'] != config.pad_token_id),
                knowledge_mask=(batch['knowledge_ids'] != config.pad_token_id)
            )
            
            loss = outputs['loss']
            
            # Gradient accumulation
            if config.gradient_accumulation_steps > 1:
                loss = loss / config.gradient_accumulation_steps
            
            loss.backward()
            
            # Track gradient norm
            grad_norm = clip_grad_norm_(model.parameters(), config.max_grad_norm)
            
            if (train_steps + 1) % config.gradient_accumulation_steps == 0:
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
            
            total_train_loss += loss.item()
            train_steps += 1
            
            # Update progress bar
            progress_bar.set_postfix({
                'loss': loss.item(),
                'grad_norm': grad_norm,
                'lr': scheduler.get_last_lr()[0]
            })
        
        avg_train_loss = total_train_loss / len(train_dataloader)
        
        # Validation
        model.eval()
        total_val_loss = 0
        
        with torch.no_grad():
            for batch in val_dataloader:
                batch = {k: v.to(device) for k, v in batch.items()}
                attention_mask = (batch['query_ids'] != config.pad_token_id)
                
                outputs = model(
                    query_ids=batch['query_ids'],
                    context_ids=batch['context_ids'],
                    knowledge_ids=batch['knowledge_ids'],
                    response_ids=batch['response_ids'],
                    query_mask=attention_mask,
                    context_mask=(batch['context_ids'] != config.pad_token_id),
                    knowledge_mask=(batch['knowledge_ids'] != config.pad_token_id)
                )
                total_val_loss += outputs['loss'].item()
        
        avg_val_loss = total_val_loss / len(val_dataloader)
        
        # Log progress
        logger.info(
            f"Epoch {epoch + 1}: "
            f"Train Loss = {avg_train_loss:.4f}, "
            f"Val Loss = {avg_val_loss:.4f}, "
            f"Grad Norm = {grad_norm:.4f}, "
            f"LR = {scheduler.get_last_lr()[0]:.2e}"
        )
        
        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            checkpoint_path = output_dir / "best_model.pt"
            
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler_state_dict': scheduler.state_dict(),
                'config': config,
                'val_loss': best_val_loss,
                'grad_norm': grad_norm
            }, checkpoint_path)
            
            logger.info(f"Saved best model to {checkpoint_path}")
        
        # Early stopping check
        if early_stopping(avg_val_loss):
            logger.info(f"Early stopping triggered after {epoch + 1} epochs")
            break
    
    logger.info("Training completed!")
    return {
        'best_val_loss': best_val_loss,
        'final_grad_norm': grad_norm,
        'epochs_trained': epoch + 1
    }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train BugSigDB conversational model")
    parser.add_argument(
        "--knowledge_base",
        type=str,
        required=True,
        help="Path to BugSigDB knowledge base CSV file"
    )
    parser.add_argument(
        "--conversation_data",
        type=str,
        required=True,
        help="Path to conversation training data JSON file"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="Directory to save model checkpoints"
    )
    parser.add_argument(
        "--num_epochs",
        type=int,
        default=10,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=3,
        help="Number of epochs to wait for improvement before early stopping"
    )
    
    args = parser.parse_args()
    
    train_conversation_model(
        knowledge_base_path=args.knowledge_base,
        conversation_data_path=args.conversation_data,
        output_dir=args.output_dir,
        num_epochs=args.num_epochs,
        patience=args.patience
    ) 