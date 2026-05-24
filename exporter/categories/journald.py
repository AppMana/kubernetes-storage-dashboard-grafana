from exporter.categories.base import DuPathCategory


class JournaldCategory(DuPathCategory):
    name = "journald"
    path = "/var/log/journal"
