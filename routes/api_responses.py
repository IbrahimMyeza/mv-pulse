from flask import jsonify, request, session, url_for


def wants_json_response():
    accept_header = request.headers.get("Accept", "")
    return (
        request.is_json
        or "application/json" in accept_header
        or request.headers.get("X-Requested-With") == "fetch"
    )


def json_success(message=None, status=200, **payload):
    body = {"ok": True}
    if message:
        body["message"] = message
    body.update(payload)
    return jsonify(body), status


def json_error(message, status=400, code="request_error", **payload):
    body = {
        "ok": False,
        "error": message,
        "code": code,
    }
    body.update(payload)
    return jsonify(body), status


def auth_required_response(message="authentication required", status=401):
    return json_error(
        message,
        status=status,
        code="auth_required",
        login_url=url_for("home"),
    )


def auth_error_or_redirect(message, redirect_endpoint="home", status=401):
    if wants_json_response():
        return auth_required_response(message=message, status=status)

    session["auth_message"] = message
    return url_for(redirect_endpoint)