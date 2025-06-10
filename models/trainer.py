import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import LambdaLR
import numpy as np
from tqdm.auto import tqdm
from typing import Dict, List, Optional
import logging
from .config import ModelConfig

class MicrobialSignatureTrainer:
    def __init__(
        self,
        model: torch.nn.Module,
        config: ModelConfig,
        train_dataloader: DataLoader,
        eval_dataloader: Optional[DataLoader] = None,
    ):
        self.model = model
        self.config = config
        self.train_dataloader = train_dataloader
        self.eval_dataloader = eval_dataloader
        
        # Setup device
        self.device = torch.device(config.device)
        self.model.to(self.device)
        
        # Setup optimizer
        self.optimizer = self._create_optimizer()
        self.scheduler = self._create_scheduler()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def _create_optimizer(self):
        """Initialize the AdamW optimizer"""
        no_decay = ["bias", "LayerNorm.weight"]
        optimizer_grouped_parameters = [
            {
                "params": [p for n, p in self.model.named_parameters() 
                          if not any(nd in n for nd in no_decay)],
                "weight_decay": self.config.weight_decay,
            },
            {
                "params": [p for n, p in self.model.named_parameters() 
                          if any(nd in n for nd in no_decay)],
                "weight_decay": 0.0,
            },
        ]
        return AdamW(optimizer_grouped_parameters, lr=self.config.learning_rate)
    
    def _create_scheduler(self):
        """Create a learning rate scheduler"""
        def lr_lambda(current_step: int):
            if current_step < self.config.warmup_steps:
                return float(current_step) / float(max(1, self.config.warmup_steps))
            return max(
                0.0,
                float(self.config.max_steps - current_step) / 
                float(max(1, self.config.max_steps - self.config.warmup_steps))
            )
        
        return LambdaLR(self.optimizer, lr_lambda)
    
    def train(self):
        """Main training loop"""
        self.model.train()
        global_step = 0
        total_loss = 0.0
        logging_loss = 0.0
        
        progress_bar = tqdm(total=self.config.max_steps, desc="Training")
        
        while global_step < self.config.max_steps:
            for batch in self.train_dataloader:
                # Move batch to device
                batch = {k: v.to(self.device) for k, v in batch.items()}
                
                # Forward pass
                outputs = self.model(
                    input_ids=batch['input_ids'],
                    attention_mask=batch['attention_mask']
                )
                
                # Calculate losses
                signature_loss = torch.nn.BCELoss()(
                    outputs['has_signature'].squeeze(),
                    batch['has_signature'].float()
                )
                
                seq_type_loss = torch.nn.CrossEntropyLoss()(
                    outputs['sequencing_type'],
                    batch['sequencing_type']
                )
                
                body_site_loss = torch.nn.CrossEntropyLoss()(
                    outputs['body_site'],
                    batch['body_site']
                )
                
                # Combined loss
                loss = signature_loss + seq_type_loss + body_site_loss
                
                # Backward pass
                if self.config.gradient_accumulation_steps > 1:
                    loss = loss / self.config.gradient_accumulation_steps
                
                loss.backward()
                
                total_loss += loss.item()
                
                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.max_grad_norm
                )
                
                # Update weights
                if (global_step + 1) % self.config.gradient_accumulation_steps == 0:
                    self.optimizer.step()
                    self.scheduler.step()
                    self.optimizer.zero_grad()
                
                # Logging
                if global_step % self.config.logging_steps == 0:
                    self.logger.info(
                        f"Step: {global_step}, Loss: {(total_loss - logging_loss) / self.config.logging_steps}"
                    )
                    logging_loss = total_loss
                
                # Evaluation
                if self.eval_dataloader is not None and global_step % self.config.eval_steps == 0:
                    eval_results = self.evaluate()
                    self.logger.info(f"Evaluation results: {eval_results}")
                    self.model.train()
                
                # Save checkpoint
                if global_step % self.config.save_steps == 0:
                    self._save_checkpoint(global_step)
                
                global_step += 1
                progress_bar.update(1)
                
                if global_step >= self.config.max_steps:
                    break
        
        progress_bar.close()
        return global_step, total_loss / global_step
    
    def evaluate(self):
        """Evaluation loop"""
        self.model.eval()
        total_eval_loss = 0
        eval_steps = 0
        
        # Metrics
        correct_signatures = 0
        total_signatures = 0
        correct_seq_types = 0
        total_seq_types = 0
        correct_body_sites = 0
        total_body_sites = 0
        
        with torch.no_grad():
            for batch in self.eval_dataloader:
                batch = {k: v.to(self.device) for k, v in batch.items()}
                
                outputs = self.model(
                    input_ids=batch['input_ids'],
                    attention_mask=batch['attention_mask']
                )
                
                # Calculate losses and metrics
                signature_preds = (outputs['has_signature'].squeeze() > 0.5).long()
                correct_signatures += (signature_preds == batch['has_signature']).sum().item()
                total_signatures += batch['has_signature'].size(0)
                
                seq_type_preds = outputs['sequencing_type'].argmax(dim=-1)
                correct_seq_types += (seq_type_preds == batch['sequencing_type']).sum().item()
                total_seq_types += batch['sequencing_type'].size(0)
                
                body_site_preds = outputs['body_site'].argmax(dim=-1)
                correct_body_sites += (body_site_preds == batch['body_site']).sum().item()
                total_body_sites += batch['body_site'].size(0)
                
                eval_steps += 1
        
        # Calculate metrics
        results = {
            'signature_accuracy': correct_signatures / total_signatures,
            'sequencing_type_accuracy': correct_seq_types / total_seq_types,
            'body_site_accuracy': correct_body_sites / total_body_sites,
        }
        
        return results
    
    def _save_checkpoint(self, step: int):
        """Save a model checkpoint"""
        checkpoint = {
            'step': step,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'config': self.config,
        }
        torch.save(checkpoint, f'checkpoint-{step}.pt')
        self.logger.info(f"Saved checkpoint at step {step}") 