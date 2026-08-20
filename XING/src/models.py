from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    id: Optional[str] = None # Hash of URL or Xing ID
    
    def to_dict(self):
        return asdict(self)
