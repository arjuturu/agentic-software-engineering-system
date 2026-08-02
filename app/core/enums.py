from enum import StrEnum


class ComponentStatus(StrEnum):
    UP = "UP"
    DOWN = "DOWN"


class RecordStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
