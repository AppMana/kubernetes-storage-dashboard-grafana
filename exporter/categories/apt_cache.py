from exporter.categories.base import DuPathCategory


class AptCacheCategory(DuPathCategory):
    name = "apt-cache"
    path = "/var/cache/apt"
