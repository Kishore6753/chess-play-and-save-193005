from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from typing_extensions import Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Human-readable error message.")


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="Unique username.")


class UserResponse(BaseModel):
    id: str = Field(..., description="User ID (UUID).")
    username: str = Field(..., description="Unique username.")
    created_at: datetime = Field(..., description="UTC timestamp when the user was created.")


GameMode = Literal["pvp", "pve"]
AISide = Literal["white", "black"]


class CreateGameRequest(BaseModel):
    white_user_id: Optional[str] = Field(None, description="User ID for white player (optional).")
    black_user_id: Optional[str] = Field(None, description="User ID for black player (optional).")

    mode: GameMode = Field(
        "pvp",
        description="Game mode: 'pvp' (human vs human) or 'pve' (human vs AI).",
    )
    ai_side: Optional[AISide] = Field(
        None,
        description="When mode='pve', which side the AI plays: 'white' or 'black'.",
    )
    ai_level: int = Field(
        1,
        ge=1,
        le=3,
        description="AI difficulty level (1-3). Higher means stronger heuristic selection.",
    )


class MoveResponse(BaseModel):
    id: str = Field(..., description="Move ID (UUID).")
    move_number: int = Field(..., description="Sequential move number starting at 1.")
    uci: str = Field(..., description="Move in UCI format, e.g. e2e4, g1f3, e7e8q.")
    san: str = Field(..., description="Move in SAN format, e.g. e4, Nf3, O-O.")
    created_at: datetime = Field(..., description="UTC timestamp when the move was created.")


class GameResponse(BaseModel):
    id: str = Field(..., description="Game ID (UUID).")
    white_user_id: Optional[str] = Field(None, description="User ID for white player.")
    black_user_id: Optional[str] = Field(None, description="User ID for black player.")

    mode: GameMode = Field(..., description="Game mode: 'pvp' or 'pve'.")
    ai_side: Optional[AISide] = Field(None, description="AI side when mode='pve'.")
    ai_level: int = Field(..., description="AI level (1-3).")

    fen: str = Field(..., description="Current board state as FEN.")
    turn: str = Field(..., description="Side to move: 'w' or 'b'.")
    status: str = Field(..., description="Game status: active/checkmate/stalemate/draw.")

    is_check: bool = Field(..., description="Whether the side to move is currently in check.")
    is_checkmate: bool = Field(..., description="Whether the position is checkmate.")
    is_stalemate: bool = Field(..., description="Whether the position is stalemate.")
    is_draw: bool = Field(..., description="Whether the game is drawn (incl. insufficient material / claimable draws).")

    moves: List[MoveResponse] = Field(default_factory=list, description="Move history.")


class SubmitMoveRequest(BaseModel):
    uci: Optional[str] = Field(
        None, description="Move in UCI format (preferred for programmatic clients)."
    )
    san: Optional[str] = Field(
        None, description="Move in SAN format (common in chess notation)."
    )


class SaveGameRequest(BaseModel):
    name: str = Field("latest", min_length=1, max_length=64, description="Snapshot name.")


class LoadGameRequest(BaseModel):
    name: str = Field("latest", min_length=1, max_length=64, description="Snapshot name to restore.")


class SnapshotResponse(BaseModel):
    id: str = Field(..., description="Snapshot ID.")
    game_id: str = Field(..., description="Associated game ID.")
    name: str = Field(..., description="Snapshot name.")
    fen: str = Field(..., description="FEN stored in snapshot.")
    move_count: int = Field(..., description="Move count when snapshot was taken.")
    created_at: datetime = Field(..., description="UTC timestamp when snapshot was created.")
