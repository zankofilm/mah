"""Javanrood migration v7.6.18 -> v7.6.19
Offline map engine migration placeholder.
Keeps operational data and map data separated.
"""

VERSION_FROM = "7.6.18"
VERSION_TO = "7.6.19"


def migrate(context=None):
    # Future schema changes are intentionally isolated here.
    # Existing main database and block data remain untouched.
    return True
