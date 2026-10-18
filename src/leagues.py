"""
leagues.py — Référentiel des compétitions : pays, drapeaux et noms officiels.

Associe les identifiants techniques des fournisseurs (The Odds API, OddsPapi)
à un nom convivial, un pays d'origine et un drapeau (emoji + drapeau SVG FlagCDN).
"""
from __future__ import annotations
from typing import Dict, Any

LEAGUES_CATALOG: Dict[str, Dict[str, str]] = {
    # Angleterre / UK
    "soccer_epl": {
        "name": "Premier League",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },
    "premier-league": {
        "name": "Premier League",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },
    "soccer_efl_champ": {
        "name": "Championship",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },
    "championship": {
        "name": "Championship",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },
    "soccer_england_league1": {
        "name": "League One",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },
    "england-league-one": {
        "name": "League One",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },
    "soccer_england_league2": {
        "name": "League Two",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },
    "england-league-two": {
        "name": "League Two",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },

    # France
    "soccer_france_ligue_one": {
        "name": "Ligue 1",
        "country": "France",
        "flag": "🇫🇷",
        "iso": "fr",
        "category": "Europe"
    },
    "ligue-1": {
        "name": "Ligue 1",
        "country": "France",
        "flag": "🇫🇷",
        "iso": "fr",
        "category": "Europe"
    },
    "soccer_france_ligue_two": {
        "name": "Ligue 2",
        "country": "France",
        "flag": "🇫🇷",
        "iso": "fr",
        "category": "Europe"
    },
    "ligue-2": {
        "name": "Ligue 2",
        "country": "France",
        "flag": "🇫🇷",
        "iso": "fr",
        "category": "Europe"
    },

    # Espagne
    "soccer_spain_la_liga": {
        "name": "La Liga",
        "country": "Espagne",
        "flag": "🇪🇸",
        "iso": "es",
        "category": "Europe"
    },
    "laliga": {
        "name": "La Liga",
        "country": "Espagne",
        "flag": "🇪🇸",
        "iso": "es",
        "category": "Europe"
    },
    "la-liga": {
        "name": "La Liga",
        "country": "Espagne",
        "flag": "🇪🇸",
        "iso": "es",
        "category": "Europe"
    },
    "la liga": {
        "name": "La Liga",
        "country": "Espagne",
        "flag": "🇪🇸",
        "iso": "es",
        "category": "Europe"
    },
    "soccer_spain_segunda_division": {
        "name": "La Liga 2",
        "country": "Espagne",
        "flag": "🇪🇸",
        "iso": "es",
        "category": "Europe"
    },
    "laliga-2": {
        "name": "La Liga 2",
        "country": "Espagne",
        "flag": "🇪🇸",
        "iso": "es",
        "category": "Europe"
    },

    # Allemagne
    "soccer_germany_bundesliga": {
        "name": "Bundesliga",
        "country": "Allemagne",
        "flag": "🇩🇪",
        "iso": "de",
        "category": "Europe"
    },
    "bundesliga": {
        "name": "Bundesliga",
        "country": "Allemagne",
        "flag": "🇩🇪",
        "iso": "de",
        "category": "Europe"
    },
    "soccer_germany_bundesliga2": {
        "name": "2. Bundesliga",
        "country": "Allemagne",
        "flag": "🇩🇪",
        "iso": "de",
        "category": "Europe"
    },
    "bundesliga-2": {
        "name": "2. Bundesliga",
        "country": "Allemagne",
        "flag": "🇩🇪",
        "iso": "de",
        "category": "Europe"
    },

    # Italie
    "soccer_italy_serie_a": {
        "name": "Serie A",
        "country": "Italie",
        "flag": "🇮🇹",
        "iso": "it",
        "category": "Europe"
    },
    "serie-a": {
        "name": "Serie A",
        "country": "Italie",
        "flag": "🇮🇹",
        "iso": "it",
        "category": "Europe"
    },
    "soccer_italy_serie_b": {
        "name": "Serie B",
        "country": "Italie",
        "flag": "🇮🇹",
        "iso": "it",
        "category": "Europe"
    },
    "serie-b": {
        "name": "Serie B",
        "country": "Italie",
        "flag": "🇮🇹",
        "iso": "it",
        "category": "Europe"
    },

    # Autres championnats européens majeurs
    "soccer_netherlands_eredivisie": {
        "name": "Eredivisie",
        "country": "Pays-Bas",
        "flag": "🇳🇱",
        "iso": "nl",
        "category": "Europe"
    },
    "eredivisie": {
        "name": "Eredivisie",
        "country": "Pays-Bas",
        "flag": "🇳🇱",
        "iso": "nl",
        "category": "Europe"
    },
    "soccer_portugal_primeira_liga": {
        "name": "Primeira Liga",
        "country": "Portugal",
        "flag": "🇵🇹",
        "iso": "pt",
        "category": "Europe"
    },
    "primeira-liga": {
        "name": "Primeira Liga",
        "country": "Portugal",
        "flag": "🇵🇹",
        "iso": "pt",
        "category": "Europe"
    },
    "soccer_belgium_first_div": {
        "name": "Jupiler Pro League",
        "country": "Belgique",
        "flag": "🇧🇪",
        "iso": "be",
        "category": "Europe"
    },
    "jupiler-pro-league": {
        "name": "Jupiler Pro League",
        "country": "Belgique",
        "flag": "🇧🇪",
        "iso": "be",
        "category": "Europe"
    },
    "soccer_turkey_super_league": {
        "name": "Süper Lig",
        "country": "Turquie",
        "flag": "🇹🇷",
        "iso": "tr",
        "category": "Europe"
    },
    "super-lig": {
        "name": "Süper Lig",
        "country": "Turquie",
        "flag": "🇹🇷",
        "iso": "tr",
        "category": "Europe"
    },
    "soccer_greece_super_league": {
        "name": "Super League",
        "country": "Grèce",
        "flag": "🇬🇷",
        "iso": "gr",
        "category": "Europe"
    },
    "super-league-greece": {
        "name": "Super League",
        "country": "Grèce",
        "flag": "🇬🇷",
        "iso": "gr",
        "category": "Europe"
    },
    "soccer_austria_bundesliga": {
        "name": "Bundesliga Autriche",
        "country": "Autriche",
        "flag": "🇦🇹",
        "iso": "at",
        "category": "Europe"
    },
    "austrian-bundesliga": {
        "name": "Bundesliga Autriche",
        "country": "Autriche",
        "flag": "🇦🇹",
        "iso": "at",
        "category": "Europe"
    },
    "soccer_switzerland_superleague": {
        "name": "Super League Suisse",
        "country": "Suisse",
        "flag": "🇨🇭",
        "iso": "ch",
        "category": "Europe"
    },
    "super-league": {
        "name": "Super League Suisse",
        "country": "Suisse",
        "flag": "🇨🇭",
        "iso": "ch",
        "category": "Europe"
    },
    "soccer_denmark_superliga": {
        "name": "Superliga",
        "country": "Danemark",
        "flag": "🇩🇰",
        "iso": "dk",
        "category": "Scandinavie"
    },
    "superliga": {
        "name": "Superliga",
        "country": "Danemark",
        "flag": "🇩🇰",
        "iso": "dk",
        "category": "Scandinavie"
    },
    "soccer_norway_eliteserien": {
        "name": "Eliteserien",
        "country": "Norvège",
        "flag": "🇳🇴",
        "iso": "no",
        "category": "Scandinavie"
    },
    "eliteserien": {
        "name": "Eliteserien",
        "country": "Norvège",
        "flag": "🇳🇴",
        "iso": "no",
        "category": "Scandinavie"
    },
    "soccer_sweden_allsvenskan": {
        "name": "Allsvenskan",
        "country": "Suède",
        "flag": "🇸🇪",
        "iso": "se",
        "category": "Scandinavie"
    },
    "allsvenskan": {
        "name": "Allsvenskan",
        "country": "Suède",
        "flag": "🇸🇪",
        "iso": "se",
        "category": "Scandinavie"
    },
    "soccer_sweden_superettan": {
        "name": "Superettan",
        "country": "Suède",
        "flag": "🇸🇪",
        "iso": "se",
        "category": "Scandinavie"
    },
    "soccer_finland_veikkausliiga": {
        "name": "Veikkausliiga",
        "country": "Finlande",
        "flag": "🇫🇮",
        "iso": "fi",
        "category": "Scandinavie"
    },
    "veikkausliiga": {
        "name": "Veikkausliiga",
        "country": "Finlande",
        "flag": "🇫🇮",
        "iso": "fi",
        "category": "Scandinavie"
    },
    "soccer_poland_ekstraklasa": {
        "name": "Ekstraklasa",
        "country": "Pologne",
        "flag": "🇵🇱",
        "iso": "pl",
        "category": "Europe"
    },
    "ekstraklasa": {
        "name": "Ekstraklasa",
        "country": "Pologne",
        "flag": "🇵🇱",
        "iso": "pl",
        "category": "Europe"
    },
    "soccer_spl": {
        "name": "Premiership",
        "country": "Écosse",
        "flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "iso": "gb-sct",
        "category": "Europe"
    },
    "scottish-premiership": {
        "name": "Premiership",
        "country": "Écosse",
        "flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "iso": "gb-sct",
        "category": "Europe"
    },
    "soccer_league_of_ireland": {
        "name": "Premier Division",
        "country": "Irlande",
        "flag": "🇮🇪",
        "iso": "ie",
        "category": "Europe"
    },
    "league-of-ireland": {
        "name": "Premier Division",
        "country": "Irlande",
        "flag": "🇮🇪",
        "iso": "ie",
        "category": "Europe"
    },

    # Compétitions continentales
    "soccer_uefa_champs_league": {
        "name": "Ligue des Champions",
        "country": "Europe (UEFA)",
        "flag": "🇪🇺",
        "iso": "eu",
        "category": "Coupes"
    },
    "soccer_uefa_europa_league": {
        "name": "Ligue Europa",
        "country": "Europe (UEFA)",
        "flag": "🇪🇺",
        "iso": "eu",
        "category": "Coupes"
    },
    "soccer_uefa_europa_conference_league": {
        "name": "Ligue Conférence",
        "country": "Europe (UEFA)",
        "flag": "🇪🇺",
        "iso": "eu",
        "category": "Coupes"
    },
    # OddsPapi numeric tournament IDs (top European & world leagues)
    "17": {
        "name": "Premier League",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },
    "8": {
        "name": "LaLiga",
        "country": "Espagne",
        "flag": "🇪🇸",
        "iso": "es",
        "category": "Europe"
    },
    "23": {
        "name": "Serie A",
        "country": "Italie",
        "flag": "🇮🇹",
        "iso": "it",
        "category": "Europe"
    },
    "35": {
        "name": "Bundesliga",
        "country": "Allemagne",
        "flag": "🇩🇪",
        "iso": "de",
        "category": "Europe"
    },
    "34": {
        "name": "Ligue 1",
        "country": "France",
        "flag": "🇫🇷",
        "iso": "fr",
        "category": "Europe"
    },
    "18": {
        "name": "Championship",
        "country": "Angleterre",
        "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "iso": "gb-eng",
        "category": "Europe"
    },
    "40": {
        "name": "Bundesliga 2",
        "country": "Allemagne",
        "flag": "🇩🇪",
        "iso": "de",
        "category": "Europe"
    },
    "53": {
        "name": "Serie B",
        "country": "Italie",
        "flag": "🇮🇹",
        "iso": "it",
        "category": "Europe"
    },
    "54": {
        "name": "LaLiga 2",
        "country": "Espagne",
        "flag": "🇪🇸",
        "iso": "es",
        "category": "Europe"
    },
    "182": {
        "name": "Ligue 2",
        "country": "France",
        "flag": "🇫🇷",
        "iso": "fr",
        "category": "Europe"
    },
    "37": {
        "name": "Eredivisie",
        "country": "Pays-Bas",
        "flag": "🇳🇱",
        "iso": "nl",
        "category": "Europe"
    },
    "20": {
        "name": "Primeira Liga",
        "country": "Portugal",
        "flag": "🇵🇹",
        "iso": "pt",
        "category": "Europe"
    },
    "52": {
        "name": "Super League",
        "country": "Turquie",
        "flag": "🇹🇷",
        "iso": "tr",
        "category": "Europe"
    },
    "41": {
        "name": "Jupiler Pro League",
        "country": "Belgique",
        "flag": "🇧🇪",
        "iso": "be",
        "category": "Europe"
    },

    # --- Amérique du Nord : USA & Canada ---
    "soccer_usa_mls": {
        "name": "MLS",
        "country": "États-Unis / Canada",
        "flag": "🇺🇸",
        "iso": "us",
        "category": "Amérique du Nord"
    },
    "mls": {
        "name": "MLS",
        "country": "États-Unis / Canada",
        "flag": "🇺🇸",
        "iso": "us",
        "category": "Amérique du Nord"
    },
    "major-league-soccer": {
        "name": "MLS",
        "country": "États-Unis / Canada",
        "flag": "🇺🇸",
        "iso": "us",
        "category": "Amérique du Nord"
    },
    "soccer_usa_usl_championship": {
        "name": "USL Championship",
        "country": "États-Unis",
        "flag": "🇺🇸",
        "iso": "us",
        "category": "Amérique du Nord"
    },
    "usl-championship": {
        "name": "USL Championship",
        "country": "États-Unis",
        "flag": "🇺🇸",
        "iso": "us",
        "category": "Amérique du Nord"
    },
    "soccer_can_pl": {
        "name": "Canadian Premier League",
        "country": "Canada",
        "flag": "🇨🇦",
        "iso": "ca",
        "category": "Amérique du Nord"
    },
    "canadian-premier-league": {
        "name": "Canadian Premier League",
        "country": "Canada",
        "flag": "🇨🇦",
        "iso": "ca",
        "category": "Amérique du Nord"
    },
    "soccer_concacaf_champions_league": {
        "name": "CONCACAF Champions Cup",
        "country": "Amérique du Nord",
        "flag": "🌎",
        "iso": "un",
        "category": "Amérique du Nord"
    },
    "concacaf-champions-cup": {
        "name": "CONCACAF Champions Cup",
        "country": "Amérique du Nord",
        "flag": "🌎",
        "iso": "un",
        "category": "Amérique du Nord"
    },

    # --- Amérique Latine : Brésil, Argentine, Mexique, Colombie, Chili... ---
    "soccer_brazil_campeonato": {
        "name": "Brasileirão Série A",
        "country": "Brésil",
        "flag": "🇧🇷",
        "iso": "br",
        "category": "Amérique Latine"
    },
    "brasileirao": {
        "name": "Brasileirão Série A",
        "country": "Brésil",
        "flag": "🇧🇷",
        "iso": "br",
        "category": "Amérique Latine"
    },
    "brasileirao-serie-a": {
        "name": "Brasileirão Série A",
        "country": "Brésil",
        "flag": "🇧🇷",
        "iso": "br",
        "category": "Amérique Latine"
    },
    "serie-a-brazil": {
        "name": "Brasileirão Série A",
        "country": "Brésil",
        "flag": "🇧🇷",
        "iso": "br",
        "category": "Amérique Latine"
    },
    "soccer_brazil_serie_b": {
        "name": "Brasileirão Série B",
        "country": "Brésil",
        "flag": "🇧🇷",
        "iso": "br",
        "category": "Amérique Latine"
    },
    "brasileirao-serie-b": {
        "name": "Brasileirão Série B",
        "country": "Brésil",
        "flag": "🇧🇷",
        "iso": "br",
        "category": "Amérique Latine"
    },
    "soccer_brazil_copa_do_brasil": {
        "name": "Copa do Brasil",
        "country": "Brésil",
        "flag": "🇧🇷",
        "iso": "br",
        "category": "Amérique Latine"
    },
    "copa-do-brasil": {
        "name": "Copa do Brasil",
        "country": "Brésil",
        "flag": "🇧🇷",
        "iso": "br",
        "category": "Amérique Latine"
    },
    "soccer_mexico_ligamx": {
        "name": "Liga MX",
        "country": "Mexique",
        "flag": "🇲🇽",
        "iso": "mx",
        "category": "Amérique Latine"
    },
    "liga-mx": {
        "name": "Liga MX",
        "country": "Mexique",
        "flag": "🇲🇽",
        "iso": "mx",
        "category": "Amérique Latine"
    },
    "mexico-liga-mx": {
        "name": "Liga MX",
        "country": "Mexique",
        "flag": "🇲🇽",
        "iso": "mx",
        "category": "Amérique Latine"
    },
    "soccer_mexico_expansion_mx": {
        "name": "Liga de Expansión MX",
        "country": "Mexique",
        "flag": "🇲🇽",
        "iso": "mx",
        "category": "Amérique Latine"
    },
    "soccer_argentina_primera_division": {
        "name": "Primera División",
        "country": "Argentine",
        "flag": "🇦🇷",
        "iso": "ar",
        "category": "Amérique Latine"
    },
    "primera-division-argentina": {
        "name": "Primera División",
        "country": "Argentine",
        "flag": "🇦🇷",
        "iso": "ar",
        "category": "Amérique Latine"
    },
    "liga-profesional-argentina": {
        "name": "Primera División",
        "country": "Argentine",
        "flag": "🇦🇷",
        "iso": "ar",
        "category": "Amérique Latine"
    },
    "soccer_argentina_copa_liga_profesional": {
        "name": "Copa de la Liga",
        "country": "Argentine",
        "flag": "🇦🇷",
        "iso": "ar",
        "category": "Amérique Latine"
    },
    "soccer_colombia_primera_a": {
        "name": "Primera A",
        "country": "Colombie",
        "flag": "🇨🇴",
        "iso": "co",
        "category": "Amérique Latine"
    },
    "liga-betplay": {
        "name": "Primera A",
        "country": "Colombie",
        "flag": "🇨🇴",
        "iso": "co",
        "category": "Amérique Latine"
    },
    "colombia-primera-a": {
        "name": "Primera A",
        "country": "Colombie",
        "flag": "🇨🇴",
        "iso": "co",
        "category": "Amérique Latine"
    },
    "soccer_chile_campeonato": {
        "name": "Primera División",
        "country": "Chili",
        "flag": "🇨🇱",
        "iso": "cl",
        "category": "Amérique Latine"
    },
    "campeonato-nacional-chile": {
        "name": "Primera División",
        "country": "Chili",
        "flag": "🇨🇱",
        "iso": "cl",
        "category": "Amérique Latine"
    },
    "soccer_peru_primera_division": {
        "name": "Liga 1",
        "country": "Pérou",
        "flag": "🇵🇪",
        "iso": "pe",
        "category": "Amérique Latine"
    },
    "soccer_ecuador_serie_a": {
        "name": "LigaPro Serie A",
        "country": "Équateur",
        "flag": "🇪🇨",
        "iso": "ec",
        "category": "Amérique Latine"
    },
    "soccer_uruguay_primera_division": {
        "name": "Primera División",
        "country": "Uruguay",
        "flag": "🇺🇾",
        "iso": "uy",
        "category": "Amérique Latine"
    },
    "soccer_conmebol_copa_libertadores": {
        "name": "Copa Libertadores",
        "country": "Amérique du Sud",
        "flag": "🏆",
        "iso": "un",
        "category": "Amérique Latine"
    },
    "copa-libertadores": {
        "name": "Copa Libertadores",
        "country": "Amérique du Sud",
        "flag": "🏆",
        "iso": "un",
        "category": "Amérique Latine"
    },
    "soccer_conmebol_copa_sudamericana": {
        "name": "Copa Sudamericana",
        "country": "Amérique du Sud",
        "flag": "🏆",
        "iso": "un",
        "category": "Amérique Latine"
    },
    "copa-sudamericana": {
        "name": "Copa Sudamericana",
        "country": "Amérique du Sud",
        "flag": "🏆",
        "iso": "un",
        "category": "Amérique Latine"
    },
}

COUNTRY_MAP: Dict[str, tuple[str, str, str]] = {
    "england": ("Angleterre", "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "gb-eng"),
    "spain": ("Espagne", "🇪🇸", "es"),
    "germany": ("Allemagne", "🇩🇪", "de"),
    "italy": ("Italie", "🇮🇹", "it"),
    "france": ("France", "🇫🇷", "fr"),
    "netherlands": ("Pays-Bas", "🇳🇱", "nl"),
    "portugal": ("Portugal", "🇵🇹", "pt"),
    "belgium": ("Belgique", "🇧🇪", "be"),
    "turkey": ("Turquie", "🇹🇷", "tr"),
    "greece": ("Grèce", "🇬🇷", "gr"),
    "austria": ("Autriche", "🇦🇹", "at"),
    "switzerland": ("Suisse", "🇨🇭", "ch"),
    "denmark": ("Danemark", "🇩🇰", "dk"),
    "norway": ("Norvège", "🇳🇴", "no"),
    "sweden": ("Suède", "🇸🇪", "se"),
    "finland": ("Finlande", "🇫🇮", "fi"),
    "poland": ("Pologne", "🇵🇱", "pl"),
    "scotland": ("Écosse", "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "gb-sct"),
    "ireland": ("Irlande", "🇮🇪", "ie"),
    "brazil": ("Brésil", "🇧🇷", "br"),
    "argentina": ("Argentine", "🇦🇷", "ar"),
    "usa": ("États-Unis", "🇺🇸", "us"),
    "mexico": ("Mexique", "🇲🇽", "mx"),
    "canada": ("Canada", "🇨🇦", "ca"),
    "colombia": ("Colombie", "🇨🇴", "co"),
    "chile": ("Chili", "🇨🇱", "cl"),
    "peru": ("Pérou", "🇵🇪", "pe"),
    "ecuador": ("Équateur", "🇪🇨", "ec"),
    "uruguay": ("Uruguay", "🇺🇾", "uy"),
    "paraguay": ("Paraguay", "🇵🇾", "py"),
    "south-america": ("Amérique du Sud", "🌎", "un"),
    "north-central-america": ("Amérique du Nord", "🌎", "un"),
    "japan": ("Japon", "🇯🇵", "jp"),
    "saudi-arabia": ("Arabie Saoudite", "🇸🇦", "sa"),
    "europe": ("Europe", "🇪🇺", "eu"),
    "international": ("International", "🌍", "un"),
}


def resolve_league(raw_key: str | None, fallback_country: str | None = None, fallback_name: str | None = None) -> Dict[str, str]:
    """
    Résout les métadonnées de la compétition à partir de n'importe quel slug ou clé brute.
    Renvoie toujours un dictionnaire avec {name, country, flag, iso, badge_url}.
    """
    if not raw_key:
        return {
            "name": fallback_name or "Général",
            "country": fallback_country or "Monde",
            "flag": "🌍",
            "iso": "un",
            "badge_url": "https://flagcdn.com/24x18/un.png"
        }

    key_normalized = str(raw_key).lower().replace(" ", "-").replace("_", "-")

    # Recherche directe
    if raw_key in LEAGUES_CATALOG:
        info = LEAGUES_CATALOG[raw_key].copy()
    elif key_normalized in LEAGUES_CATALOG:
        info = LEAGUES_CATALOG[key_normalized].copy()
    else:
        # Recherche par sous-chaîne
        match_found = None
        for k, v in LEAGUES_CATALOG.items():
            if k in key_normalized or key_normalized in k or v["name"].lower() in key_normalized:
                match_found = v.copy()
                break
        if match_found:
            info = match_found
        else:
            # Fallback lisible avec enrichissement pays
            clean_name = fallback_name or str(raw_key).replace("soccer_", "").replace("_", " ").title()
            country_name = "International"
            flag = "⚽"
            iso_code = "un"
            
            if fallback_country:
                cat_key = str(fallback_country).lower().strip().replace(" ", "-")
                if cat_key in COUNTRY_MAP:
                    country_name, flag, iso_code = COUNTRY_MAP[cat_key]
                else:
                    country_name = fallback_country.title()

            info = {
                "name": clean_name,
                "country": country_name,
                "flag": flag,
                "iso": iso_code,
                "category": "Autre"
            }

    # URL du drapeau haute définition via FlagCDN (gratuit, public, ultra-rapide)
    iso_code = info.get("iso", "un")
    info["badge_url"] = f"https://flagcdn.com/24x18/{iso_code}.png"
    return info
