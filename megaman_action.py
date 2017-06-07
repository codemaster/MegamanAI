"""Actions that X can take"""

from enum import Enum

class MegamanAction(Enum):
    """Enum of possible actions"""
    MOVE_RIGHT = 1
    MOVE_LEFT = 2
    STOP_MOVEMENT = 3
    JUMP = 4
    SHOOT = 5
    CHARGE = 6
    DASH = 7
    CHANGE_WEAPON = 8
    START = 9
