from dataclasses import dataclass, field
from typing import List
from abc import ABC, abstractmethod
from .asset import Asset



@dataclass
class Portfolio:
    name: str
    positions: List['Position'] = field(default_factory=list)

    def add_position(self, position: 'Position'):
        if position.quantity <= 0:
            raise ValueError("quantity must be positive")
        self.positions.append(position)

    def del_position(self, position: 'Position'):
        if position not in self.positions:
            raise ValueError("Position not found")
        self.positions.remove(position)

    def total_value(self) -> float:
        return sum(position.total_value() for position in self.positions)

    def total_pnl(self) -> float:
        return sum(position.calculate_pnl() for position in self.positions)

    def __getitem__(self, index: int) -> 'Position':
        return self.positions[index]

@dataclass
class Position(ABC):
    asset: 'Asset'
    quantity: float = 1

    @abstractmethod
    def calculate_pnl(self) -> float:
        pass

    def total_value(self) -> float:
        return self.asset.get_current_price * self.quantity

@dataclass
class LongPosition(Position):

    entry_price: float = None
    def __post_init__(self):
        if self.entry_price is None:
            self.entry_price = self.asset.get_current_price

    def calculate_pnl(self) -> float:
        return (self.asset.get_current_price - self.entry_price) * self.quantity

@dataclass
class ShortPosition(Position):

    entry_price: float = None

    def __post_init__(self):
        if self.entry_price is None:
            self.entry_price = self.asset.get_current_price

    def calculate_pnl(self) -> float:
        return (self.entry_price - self.asset.get_current_price) * self.quantity
