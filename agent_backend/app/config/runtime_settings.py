from .config import SQL_AGENTDB_URI as _default_sql_uri

_settings: dict = {
    "sql_agent_db_uri": _default_sql_uri,
}


def get_sql_agent_db_uri() -> str:
    return _settings["sql_agent_db_uri"]


def set_sql_agent_db_uri(uri: str) -> None:
    _settings["sql_agent_db_uri"] = uri
