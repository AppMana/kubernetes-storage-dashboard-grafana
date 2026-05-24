from exporter.categories.base import DuPathCategory


class DockerdCategory(DuPathCategory):
    name = "dockerd"
    path = "/var/lib/docker"
