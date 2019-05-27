from flask import request, redirect, url_for, abort, jsonify
from CTFd.utils import config, get_config
from CTFd.cache import cache
from CTFd.utils.dates import ctf_ended, ctf_started, ctftime, view_after_ctf
from CTFd.utils import user as current_user
from CTFd.utils.user import get_current_team, is_admin, authed
from CTFd.utils.modes import TEAMS_MODE
import functools


def during_ctf_time_only(f):
    """
    Decorator to restrict an endpoint to only be seen during a CTF
    :param f:
    :return:
    """

    @functools.wraps(f)
    def during_ctf_time_only_wrapper(*args, **kwargs):
        if ctftime() or current_user.is_admin():
            return f(*args, **kwargs)
        else:
            if ctf_ended():
                if view_after_ctf():
                    return f(*args, **kwargs)
                else:
                    error = "{} has ended".format(config.ctf_name())
                    abort(403, description=error)
            if ctf_started() is False:
                error = "{} has not started yet".format(config.ctf_name())
                abort(403, description=error)

    return during_ctf_time_only_wrapper


def require_authentication_if_config(config_key):
    def _require_authentication_if_config(f):
        @functools.wraps(f)
        def __require_authentication_if_config(*args, **kwargs):
            value = get_config(config_key)
            if value and current_user.authed():
                return redirect(url_for("auth.login", next=request.full_path))
            else:
                return f(*args, **kwargs)

        return __require_authentication_if_config

    return _require_authentication_if_config


def require_verified_emails(f):
    """
    Decorator to restrict an endpoint to users with confirmed active email addresses
    :param f:
    :return:
    """

    @functools.wraps(f)
    def _require_verified_emails(*args, **kwargs):
        if get_config("verify_emails"):
            if current_user.authed():
                if (
                    current_user.is_admin() is False
                    and current_user.is_verified() is False
                ):  # User is not confirmed
                    if request.content_type == "application/json":
                        abort(403)
                    else:
                        return redirect(url_for("auth.confirm"))
        return f(*args, **kwargs)

    return _require_verified_emails


def authed_only(f):
    """
    Decorator that requires the user to be authenticated
    :param f:
    :return:
    """

    @functools.wraps(f)
    def authed_only_wrapper(*args, **kwargs):
        if authed():
            return f(*args, **kwargs)
        else:
            if request.content_type == "application/json":
                abort(403)
            else:
                return redirect(url_for("auth.login", next=request.full_path))

    return authed_only_wrapper


def admins_only(f):
    """
    Decorator that requires the user to be authenticated and an admin
    :param f:
    :return:
    """

    @functools.wraps(f)
    def admins_only_wrapper(*args, **kwargs):
        if is_admin():
            return f(*args, **kwargs)
        else:
            if request.content_type == "application/json":
                abort(403)
            else:
                return redirect(url_for("auth.login", next=request.full_path))

    return admins_only_wrapper


def require_team(f):
    @functools.wraps(f)
    def require_team_wrapper(*args, **kwargs):
        if get_config("user_mode") == TEAMS_MODE:
            team = get_current_team()
            if team is None:
                return redirect(url_for("teams.private", next=request.full_path))
        return f(*args, **kwargs)

    return require_team_wrapper


def ratelimit(method="POST", limit=50, interval=300, key_prefix="rl"):
    def ratelimit_decorator(f):
        @functools.wraps(f)
        def ratelimit_function(*args, **kwargs):
            ip_address = current_user.get_ip()
            key = "{}:{}:{}".format(key_prefix, ip_address, request.endpoint)
            current = cache.get(key)

            if request.method == method:
                if (
                    current and int(current) > limit - 1
                ):  # -1 in order to align expected limit with the real value
                    resp = jsonify(
                        {
                            "code": 429,
                            "message": "Too many requests. Limit is %s requests in %s seconds"
                            % (limit, interval),
                        }
                    )
                    resp.status_code = 429
                    return resp
                else:
                    if current is None:
                        cache.set(key, 1, timeout=interval)
                    else:
                        cache.set(key, int(current) + 1, timeout=interval)
            return f(*args, **kwargs)

        return ratelimit_function

    return ratelimit_decorator
