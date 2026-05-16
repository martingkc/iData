from flask import jsonify, request

from ...config.runtime_settings import get_sql_agent_db_uri, set_sql_agent_db_uri
from ...services.agent.orchestrator_agent.tools import reset_sql_agent
from ...routes.auth_routes.auth_extensions import token_auth
from . import settings_bp


@settings_bp.get("/settings")
@token_auth.login_required
def get_settings():
    return jsonify({"sql_agent_db_uri": get_sql_agent_db_uri()})


@settings_bp.post("/settings")
@token_auth.login_required
def update_settings():
    payload = request.get_json(force=True) or {}
    uri = payload.get("sql_agent_db_uri", "").strip()
    if not uri:
        return jsonify({"error": "sql_agent_db_uri is required"}), 400
    set_sql_agent_db_uri(uri)
    reset_sql_agent()
    return jsonify({"sql_agent_db_uri": uri})
