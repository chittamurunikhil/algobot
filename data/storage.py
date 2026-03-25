"""
SQLite storage layer — handles persistence for watchlists, trades, and settings.
Uses raw SQLite for simplicity and speed.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional
from data.models import Watchlist, TradeRecord, TradeStatus, OrderSide


class Database:
    """SQLite database manager with WAL mode for concurrent reads."""

    def __init__(self, db_path: str = "data/algobot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                symbols TEXT NOT NULL DEFAULT '[]',
                segment TEXT NOT NULL DEFAULT 'intraday',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                segment TEXT NOT NULL DEFAULT 'intraday',
                mode TEXT NOT NULL DEFAULT 'prediction',
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity INTEGER NOT NULL,
                lot_size INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'PENDING',
                pnl REAL NOT NULL DEFAULT 0.0,
                commission REAL NOT NULL DEFAULT 0.0,
                confidence_score REAL NOT NULL DEFAULT 0.0,
                stop_loss REAL NOT NULL DEFAULT 0.0,
                take_profit REAL NOT NULL DEFAULT 0.0,
                strategy_notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                closed_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Create index for trade queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_segment ON trades(segment)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at)")

        self.conn.commit()

    # ── Watchlist Operations ─────────────────────────────────────────────

    def save_watchlist(self, wl: Watchlist) -> Watchlist:
        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT OR REPLACE INTO watchlists (id, name, symbols, segment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (wl.id, wl.name, json.dumps(wl.symbols), wl.segment,
              wl.created_at.isoformat() if isinstance(wl.created_at, datetime) else wl.created_at, now))
        self.conn.commit()
        wl.updated_at = datetime.fromisoformat(now)
        return wl

    def get_watchlist(self, wl_id: int) -> Optional[Watchlist]:
        row = self.conn.execute("SELECT * FROM watchlists WHERE id = ?", (wl_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_watchlist(row)

    def get_all_watchlists(self) -> List[Watchlist]:
        rows = self.conn.execute("SELECT * FROM watchlists ORDER BY id").fetchall()
        return [self._row_to_watchlist(r) for r in rows]

    def delete_watchlist(self, wl_id: int) -> bool:
        cursor = self.conn.execute("DELETE FROM watchlists WHERE id = ?", (wl_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def _row_to_watchlist(self, row) -> Watchlist:
        return Watchlist(
            id=row["id"],
            name=row["name"],
            symbols=json.loads(row["symbols"]),
            segment=row["segment"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ── Trade Operations ─────────────────────────────────────────────────

    def save_trade(self, trade: TradeRecord) -> TradeRecord:
        self.conn.execute("""
            INSERT OR REPLACE INTO trades
            (id, symbol, segment, mode, side, entry_price, exit_price, quantity, lot_size,
             status, pnl, commission, confidence_score, stop_loss, take_profit,
             strategy_notes, created_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.id, trade.symbol, trade.segment, trade.mode,
            trade.side.value if isinstance(trade.side, OrderSide) else trade.side,
            trade.entry_price, trade.exit_price, trade.quantity, trade.lot_size,
            trade.status.value if isinstance(trade.status, TradeStatus) else trade.status,
            trade.pnl, trade.commission, trade.confidence_score,
            trade.stop_loss, trade.take_profit, trade.strategy_notes,
            trade.created_at.isoformat() if isinstance(trade.created_at, datetime) else trade.created_at,
            trade.closed_at.isoformat() if isinstance(trade.closed_at, datetime) else trade.closed_at,
        ))
        self.conn.commit()
        return trade

    def get_trades(self, symbol: str = None, segment: str = None,
                   status: str = None, limit: int = 100) -> List[TradeRecord]:
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if segment:
            query += " AND segment = ?"
            params.append(segment)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_trade(r) for r in rows]

    def get_open_trades(self) -> List[TradeRecord]:
        return self.get_trades(status="OPEN")

    def get_today_trades(self) -> List[TradeRecord]:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT * FROM trades WHERE created_at >= ? ORDER BY created_at DESC",
            (today,)
        ).fetchall()
        return [self._row_to_trade(r) for r in rows]

    def get_pnl_summary(self) -> dict:
        """Calculate P&L summary across different time periods."""
        today = datetime.now().strftime("%Y-%m-%d")

        today_pnl = self.conn.execute(
            "SELECT COALESCE(SUM(pnl), 0) as total FROM trades WHERE created_at >= ? AND status = 'CLOSED'",
            (today,)
        ).fetchone()["total"]

        total_pnl = self.conn.execute(
            "SELECT COALESCE(SUM(pnl), 0) as total FROM trades WHERE status = 'CLOSED'"
        ).fetchone()["total"]

        total_commission = self.conn.execute(
            "SELECT COALESCE(SUM(commission), 0) as total FROM trades WHERE status = 'CLOSED'"
        ).fetchone()["total"]

        win_count = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM trades WHERE status = 'CLOSED' AND pnl > 0"
        ).fetchone()["cnt"]

        loss_count = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM trades WHERE status = 'CLOSED' AND pnl <= 0"
        ).fetchone()["cnt"]

        total_trades = win_count + loss_count

        return {
            "today_pnl": today_pnl,
            "total_pnl": total_pnl,
            "total_commission": total_commission,
            "win_count": win_count,
            "loss_count": loss_count,
            "total_trades": total_trades,
            "win_rate": (win_count / total_trades * 100) if total_trades > 0 else 0.0,
        }

    def _row_to_trade(self, row) -> TradeRecord:
        return TradeRecord(
            id=row["id"],
            symbol=row["symbol"],
            segment=row["segment"],
            mode=row["mode"],
            side=OrderSide(row["side"]),
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            quantity=row["quantity"],
            lot_size=row["lot_size"],
            status=TradeStatus(row["status"]),
            pnl=row["pnl"],
            commission=row["commission"],
            confidence_score=row["confidence_score"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            strategy_notes=row["strategy_notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            closed_at=datetime.fromisoformat(row["closed_at"]) if row["closed_at"] else None,
        )

    # ── Settings ─────────────────────────────────────────────────────────

    def set_setting(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def close(self):
        self.conn.close()


# Singleton
_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        from config.settings import get_settings
        settings = get_settings()
        _db = Database(settings.db_path)
    return _db
