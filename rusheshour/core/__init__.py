"""
Noyau fonctionnel RushesHour — sans dépendance Qt ni CLI.

Toutes les fonctions opèrent sur des objets Path et des structures Python
standard ; elles sont utilisables indépendamment de la GUI ou du CLI.
"""

from rusheshour.core.session import Session
from rusheshour.core.scanner import collect_videos, VIDEO_EXTENSIONS
from rusheshour.core.probe   import (
    get_video_info,
    check_errors,
    is_already_mp4,
    format_duration,
    print_video_info,
)
from rusheshour.core.repair  import action_repair, REPAIR_STRATEGIES
from rusheshour.core.convert import action_convert_mp4, FFMPEG_ENCODE_FLAGS
from rusheshour.core.actions import (
    action_rename,
    action_move_to,
    action_move_manual,
    action_delete,
    finalize,
)

__all__ = [
    # Session
    "Session",
    # Scanner
    "collect_videos",
    "VIDEO_EXTENSIONS",
    # Probe
    "get_video_info",
    "check_errors",
    "is_already_mp4",
    "format_duration",
    "print_video_info",
    # Repair
    "action_repair",
    "REPAIR_STRATEGIES",
    # Convert
    "action_convert_mp4",
    "FFMPEG_ENCODE_FLAGS",
    # Actions
    "action_rename",
    "action_move_to",
    "action_move_manual",
    "action_delete",
    "finalize",
]
