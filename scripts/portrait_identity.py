"""Identity aliases between the names used by upstream feeds and portrait files."""

# Maps a normalized portrait slug to the slug of the same person whose
# verified face crop already exists. Only add entries after confirming that both
# names refer to one driver.
PORTRAIT_ALIASES = {
    "benji-goethe": "benjamin-goethe",
}

# Official source name used by the portrait feeds when it differs from the
# name used by the series standings.
SOURCE_NAME_ALIASES = {
    "albert costa": "Albert Costa Balboa",
}
