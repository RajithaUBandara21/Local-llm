import app.main


def route_methods():
    paths = app.main.app.openapi()["paths"]
    return {
        (path, method.upper())
        for path, operations in paths.items()
        for method in operations
    }


EXPECTED_ROUTES = {
    ("/health", "GET"),
    ("/api/chat", "POST"),
    ("/api/models", "GET"),
    ("/api/model/active", "GET"),
    ("/api/model/change", "POST"),
    ("/api/settings/temperature", "POST"),
    ("/api/triage", "POST"),
    ("/api/gmail/oauth/connect", "POST"),
    ("/api/gmail/oauth/callback", "GET"),
    ("/api/gmail/status", "GET"),
    ("/api/gmail/oauth/disconnect", "POST"),
    ("/api/batches", "POST"),
    ("/api/batches", "GET"),
    ("/api/batches/{batch_id}", "GET"),
    ("/api/batches/{batch_id}/resume", "POST"),
    ("/api/batches/{batch_id}/pending-preview", "GET"),
    ("/api/batches/{batch_id}/stop", "POST"),
    ("/api/batches/{batch_id}", "DELETE"),
    ("/api/mailbox-files", "POST"),
    ("/api/mailbox-files", "GET"),
    ("/api/mailbox-files/{file}", "DELETE"),
    ("/api/mailbox-files/{file}/preview", "GET"),
    ("/api/bulk-insert", "POST"),
    ("/api/emails", "GET"),
    ("/api/emails/{email_id}/review", "POST"),
}


def test_the_composition_root_wires_every_documented_route():
    actual = route_methods()

    missing = EXPECTED_ROUTES - actual
    assert missing == set(), f"Routes missing from app.main: {missing}"


def test_cors_middleware_is_installed():
    middleware_classes = {m.cls.__name__ for m in app.main.app.user_middleware}
    assert "CORSMiddleware" in middleware_classes
