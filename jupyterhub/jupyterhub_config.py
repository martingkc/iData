import os

c = get_config()  # noqa: F821


# Lightweight single-container setup (not for production hardening)
c.JupyterHub.spawner_class = 'dockerspawner.DockerSpawner'
c.JupyterHub.hub_ip = 'jupyterhub'
c.JupyterHub.hub_port = 8080


c.JupyterHub.authenticator_class = "dummy"
c.DummyAuthenticator.password = os.environ.get("JUPYTERHUB_PASSWORD", "changeme")
c.Authenticator.admin_users = {os.environ.get("JUPYTERHUB_ADMIN_USER", "admin")}

# Avoid requiring real system users in this container
c.JupyterHub.spawner_class = "simple"

# Persist hub state in mounted volume
c.JupyterHub.db_url = "sqlite:///jupyterhub.sqlite"

# Single-user defaults
c.Spawner.default_url = "/lab"
c.Spawner.notebook_dir = "/srv/shared"

c.Spawner.args = ["--allow-root"]


# Enable token authentication in URLs for API access
c.Spawner.environment = {
    'JUPYTERHUB_ALLOW_TOKEN_IN_URL': '1'
}

# Optional: Configure single-user server to start on a specific port
# c.Spawner.port = 8888

# Optional: Ensure the MCP server extension is enabled
c.ServerApp.jpserver_extensions = {
    'jupyter_mcp_server': True
}