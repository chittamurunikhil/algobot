"""
Watchlist Manager — CRUD operations for 10 watchlists × 50–200 stocks each.
"""
from datetime import datetime
from typing import List, Optional
from data.models import Watchlist
from data.storage import get_db


class WatchlistManager:
    """Manage up to 10 named watchlists with 50–200 symbols each."""

    MAX_WATCHLISTS = 10
    MAX_SYMBOLS_PER_LIST = 200
    MIN_SYMBOLS_PER_LIST = 0  # Allow empty lists

    def __init__(self):
        self.db = get_db()

    def create_watchlist(self, wl_id: int, name: str,
                         segment: str = "intraday") -> Watchlist:
        """Create a new watchlist (ID must be 1–10)."""
        if not 1 <= wl_id <= self.MAX_WATCHLISTS:
            raise ValueError(f"Watchlist ID must be between 1 and {self.MAX_WATCHLISTS}")

        existing = self.db.get_watchlist(wl_id)
        if existing:
            raise ValueError(f"Watchlist {wl_id} already exists: '{existing.name}'")

        wl = Watchlist(
            id=wl_id,
            name=name,
            symbols=[],
            segment=segment,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        return self.db.save_watchlist(wl)

    def get_watchlist(self, wl_id: int) -> Optional[Watchlist]:
        """Get a watchlist by ID."""
        return self.db.get_watchlist(wl_id)

    def get_all_watchlists(self) -> List[Watchlist]:
        """Get all watchlists."""
        return self.db.get_all_watchlists()

    def update_watchlist_name(self, wl_id: int, name: str) -> Watchlist:
        """Rename a watchlist."""
        wl = self._get_or_raise(wl_id)
        wl.name = name
        wl.updated_at = datetime.now()
        return self.db.save_watchlist(wl)

    def delete_watchlist(self, wl_id: int) -> bool:
        """Delete a watchlist."""
        return self.db.delete_watchlist(wl_id)

    def add_symbol(self, wl_id: int, symbol: str) -> Watchlist:
        """Add a symbol to a watchlist."""
        wl = self._get_or_raise(wl_id)
        symbol = symbol.upper().strip()

        if symbol in wl.symbols:
            return wl  # Already exists

        if wl.is_full():
            raise ValueError(f"Watchlist '{wl.name}' is full ({self.MAX_SYMBOLS_PER_LIST} symbols max)")

        wl.symbols.append(symbol)
        wl.updated_at = datetime.now()
        return self.db.save_watchlist(wl)

    def add_symbols_bulk(self, wl_id: int, symbols: List[str]) -> Watchlist:
        """Add multiple symbols at once."""
        wl = self._get_or_raise(wl_id)
        for sym in symbols:
            sym = sym.upper().strip()
            if sym and sym not in wl.symbols and len(wl.symbols) < self.MAX_SYMBOLS_PER_LIST:
                wl.symbols.append(sym)
        wl.updated_at = datetime.now()
        return self.db.save_watchlist(wl)

    def remove_symbol(self, wl_id: int, symbol: str) -> Watchlist:
        """Remove a symbol from a watchlist."""
        wl = self._get_or_raise(wl_id)
        symbol = symbol.upper().strip()
        if symbol in wl.symbols:
            wl.symbols.remove(symbol)
            wl.updated_at = datetime.now()
            return self.db.save_watchlist(wl)
        return wl

    def reorder_symbols(self, wl_id: int, symbols: List[str]) -> Watchlist:
        """Replace the symbol list with a reordered version."""
        wl = self._get_or_raise(wl_id)
        wl.symbols = [s.upper().strip() for s in symbols]
        wl.updated_at = datetime.now()
        return self.db.save_watchlist(wl)

    def import_csv(self, wl_id: int, csv_content: str) -> Watchlist:
        """Import symbols from CSV string (one per line or comma-separated)."""
        symbols = []
        for line in csv_content.strip().split("\n"):
            for sym in line.split(","):
                sym = sym.strip().upper()
                if sym:
                    symbols.append(sym)
        return self.add_symbols_bulk(wl_id, symbols)

    def export_csv(self, wl_id: int) -> str:
        """Export watchlist symbols as CSV string."""
        wl = self._get_or_raise(wl_id)
        return "\n".join(wl.symbols)

    def _get_or_raise(self, wl_id: int) -> Watchlist:
        wl = self.db.get_watchlist(wl_id)
        if wl is None:
            raise ValueError(f"Watchlist {wl_id} not found")
        return wl
