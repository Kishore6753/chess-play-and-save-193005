from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base SQLAlchemy declarative class."""


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """A user who can participate in chess games."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

    games_as_white: Mapped[List["Game"]] = relationship(
        back_populates="white_user",
        foreign_keys="Game.white_user_id",
    )
    games_as_black: Mapped[List["Game"]] = relationship(
        back_populates="black_user",
        foreign_keys="Game.black_user_id",
    )


class Game(Base):
    """A chess game, storing the current board state as FEN plus history of moves."""

    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    white_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    black_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # Current game state
    fen: Mapped[str] = mapped_column(Text, default="startpos")
    status: Mapped[str] = mapped_column(String(32), default="active")  # active/checkmate/stalemate/draw
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow)

    white_user: Mapped[Optional["User"]] = relationship(
        back_populates="games_as_white",
        foreign_keys=[white_user_id],
    )
    black_user: Mapped[Optional["User"]] = relationship(
        back_populates="games_as_black",
        foreign_keys=[black_user_id],
    )

    moves: Mapped[List["Move"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        order_by="Move.move_number",
    )

    snapshots: Mapped[List["GameSnapshot"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        order_by="GameSnapshot.created_at",
    )


class Move(Base):
    """A move applied to a game, persisted with SAN/UCI and before/after FEN."""

    __tablename__ = "moves"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    game_id: Mapped[str] = mapped_column(String(36), ForeignKey("games.id", ondelete="CASCADE"), index=True)

    move_number: Mapped[int] = mapped_column(Integer, index=True)
    uci: Mapped[str] = mapped_column(String(16))
    san: Mapped[str] = mapped_column(String(32))

    fen_before: Mapped[str] = mapped_column(Text)
    fen_after: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

    game: Mapped["Game"] = relationship(back_populates="moves")


class GameSnapshot(Base):
    """A named snapshot of a game for explicit save/load operations."""

    __tablename__ = "game_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    game_id: Mapped[str] = mapped_column(String(36), ForeignKey("games.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(64), default="latest", index=True)
    fen: Mapped[str] = mapped_column(Text)

    # Number of moves that existed when the snapshot was taken.
    move_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

    game: Mapped["Game"] = relationship(back_populates="snapshots")
