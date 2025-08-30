import datetime
from typing import Any


class Pet:
    name: str
    born_at: datetime.datetime
    last_prize: datetime.datetime
    
    _stats: dict[Any, Any]

    def __init__(self, pet_data: dict[Any, Any]):
        self.name = pet_data["name"]
        self.born_at = datetime.datetime.fromisoformat(pet_data["born_at"])
        
        if not pet_data["last_prize"]:
            # get January 1, 1970'd
            self.last_prize = datetime.datetime.fromtimestamp(0)
        else:
            self.last_prize = datetime.datetime.fromisoformat(pet_data["last_prize"])
        
        self._stats= pet_data["stats"]
    
    def get_stat(self, name):
        return self._stats[name]
    
    def get_stat_value(self, name) -> int:
        return self._stats[name]["stat_value"]
    
    @property
    def money(self):
        return self.get_stat_value("money")
    
    @property
    def willpower(self):
        return self.get_stat_value("willpower")
    
    @property
    def hunger(self):
        return self.get_stat_value("hunger")
    
    @property
    def cleanliness(self):
        return self.get_stat_value("cleanliness")
    
    @property
    def happiness(self):
        return self.get_stat_value("happiness")