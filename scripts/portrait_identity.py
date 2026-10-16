"""Identity aliases between the names used by upstream feeds and portrait files."""

# Maps a normalized portrait slug to the slug of the same person whose
# verified face crop already exists. Only add entries after confirming that both
# names refer to one driver.
PORTRAIT_ALIASES = {
    "benji-goethe": "benjamin-goethe",
    "nicolas-varrone": "nico-varrone",
}

# Official studio portraits the collectors cannot discover automatically
# (driver no longer listed on the current roster page, or the official file
# name spells the name differently).
MANUAL_SOURCES = {
    "yuki-tsunoda": "https://media.formula1.com/image/upload/c_lfill,w_1024/q_auto/v1740000001/common/f1/2026/racingbulls/yuktsu01/2026racingbullsyuktsu01right.webp",
    "nicholas-monteiro": "https://indynxt-cdn.azureedge.net/-/media/IndyCar/Drivers/INDY-NXT/Driver-List/NicolasMonteiro.jpg",
    # FIA WEC 2025 profile; the upload file name does not contain his name.
    "michael-christensen": "https://www.fiawec.com/uploads/2-d58f99-697a311686989440950556.png",
}

# Official source name used by the portrait feeds when it differs from the
# name used by the series standings.
SOURCE_NAME_ALIASES = {
    "albert costa": "Albert Costa Balboa",
}
