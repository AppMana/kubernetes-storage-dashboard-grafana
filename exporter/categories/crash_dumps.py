from exporter.categories.base import DuPathCategory


class CrashDumpsCategory(DuPathCategory):
    name = "crash-dumps"
    path = "/var/crash"
