from typing import Dict, Optional, List
import json
from pathlib import Path
from datetime import datetime

class ChatMemory:
    """Class to store chat history and context."""
    
    def __init__(self, max_messages: int = 100):
        self.messages: List[Dict] = []
        self.max_messages = max_messages
    
    def add_message(self, role: str, content: str):
        """Add a message to the chat history."""
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        # Trim if needed
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
    def clear(self):
        """Clear chat history."""
        self.messages = []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'messages': self.messages,
            'max_messages': self.max_messages
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ChatMemory':
        """Create from dictionary."""
        memory = cls(max_messages=data.get('max_messages', 100))
        memory.messages = data.get('messages', [])
        return memory

class UserSession:
    def __init__(self, name: str):
        self.name = name
        self.session_start = datetime.now()
        self.preferences = {}
        self.coding_languages = set()
        self.current_paper = None  # Current paper PMID
        self.paper_history = []    # History of analyzed papers
        self.memory = ChatMemory() # Chat memory
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'session_start': self.session_start.isoformat(),
            'preferences': self.preferences,
            'coding_languages': list(self.coding_languages),
            'current_paper': self.current_paper,
            'paper_history': self.paper_history,
            'memory': self.memory.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserSession':
        session = cls(data['name'])
        session.session_start = datetime.fromisoformat(data['session_start'])
        session.preferences = data['preferences']
        session.coding_languages = set(data['coding_languages'])
        session.current_paper = data.get('current_paper')
        session.paper_history = data.get('paper_history', [])
        
        if 'memory' in data:
            session.memory = ChatMemory.from_dict(data['memory'])
        
        return session
    
    def set_current_paper(self, pmid: str):
        """Set the current paper being analyzed."""
        self.current_paper = pmid
        if pmid not in self.paper_history:
            self.paper_history.append(pmid)
    
    def update_preferences(self, preferences: Dict):
        """Update user preferences"""
        self.preferences.update(preferences)
    
    def add_coding_language(self, language: str):
        """Add preferred coding language"""
        self.coding_languages.add(language)

class UserManager:
    def __init__(self, storage_path: str = 'user_sessions'):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.active_sessions: Dict[str, UserSession] = {}
    
    def start_session(self, name: str) -> UserSession:
        """Start a new user session or load existing one"""
        if name in self.active_sessions:
            return self.active_sessions[name]
        
        # Try to load existing session
        session_file = self.storage_path / f"{name}.json"
        if session_file.exists():
            with open(session_file, 'r') as f:
                data = json.load(f)
                session = UserSession.from_dict(data)
        else:
            session = UserSession(name)
        
        self.active_sessions[name] = session
        return session
    
    def save_session(self, name: str):
        """Save user session to disk"""
        if name not in self.active_sessions:
            return
        
        session = self.active_sessions[name]
        session_file = self.storage_path / f"{name}.json"
        with open(session_file, 'w') as f:
            json.dump(session.to_dict(), f, indent=2)
    
    def get_session(self, name: str) -> Optional[UserSession]:
        """Get active user session"""
        return self.active_sessions.get(name)
    
    def end_session(self, name: str):
        """End and save user session"""
        if name in self.active_sessions:
            self.save_session(name)
            del self.active_sessions[name]
    
    def update_preferences(self, name: str, preferences: Dict):
        """Update user preferences"""
        if name in self.active_sessions:
            self.active_sessions[name].preferences.update(preferences)
            self.save_session(name)
    
    def add_coding_language(self, name: str, language: str):
        """Add preferred coding language"""
        if name in self.active_sessions:
            self.active_sessions[name].coding_languages.add(language)
            self.save_session(name) 