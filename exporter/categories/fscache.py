from exporter.categories.base import DuPathCategory


class FscacheCategory(DuPathCategory):
    """NFS / SMB client filesystem cache (`cachefilesd`)."""
    name = "fscache"
    path = "/var/cache/fscache"
