from distutils.version import StrictVersion
from flask import current_app as app
from CTFd.utils import get_config, set_config, get_app_config
from CTFd.utils.config import is_setup
from CTFd.models import db, Challenges, Users, Teams
from CTFd.utils.security.passwords import sha256
from platform import python_version
import requests
import time
import sys
import os


def update_check(force=False):
    """
    Makes a request to ctfd.io to check if there is a new version of CTFd available. The service is provided in return
    for users opting in to anonymous usage data collection. Users can opt-out of update checks by specifying
    UPDATE_CHECK = False in config.py

    :param force:
    :return:
    """
    # If UPDATE_CHECK is disabled don't check for updates at all.
    if app.config.get('UPDATE_CHECK') is False:
        return

    # Don't do an update check if not setup
    if is_setup() is False:
        return

    # Get when we should check for updates next.
    next_update_check = get_config('next_update_check') or 0

    # If we have passed our saved time or we are forcing we should check.
    update = (next_update_check < time.time()) or force

    if update:
        try:
            name = str(get_config('ctf_name')) or ''
            params = {
                'ctf_id': sha256(name),
                'current': app.VERSION,
                'python_version_raw': sys.hexversion,
                'python_version': python_version(),
                'db_driver': db.session.bind.dialect.name,
                'challenge_count': Challenges.query.count(),
                'user_mode': get_config('user_mode'),
                'user_count': Users.query.count(),
                'team_count': Teams.query.count(),
                'theme': get_config('ctf_theme'),
                'upload_provider': get_app_config('UPLOAD_PROVIDER')
            }
            check = requests.post(
                'https://versioning.ctfd.io/',
                json=params,
                timeout=0.1
            ).json()
        except requests.exceptions.RequestException as e:
            pass
        except ValueError as e:
            pass
        else:
            try:
                latest = check['resource']['tag']
                html_url = check['resource']['html_url']
                if StrictVersion(latest) > StrictVersion(app.VERSION):
                    set_config('version_latest', html_url)
                elif StrictVersion(latest) <= StrictVersion(app.VERSION):
                    set_config('version_latest', None)
                next_update_check_time = check['resource'].get('next', int(time.time() + 43200))
                set_config('next_update_check', next_update_check_time)
            except KeyError:
                set_config('version_latest', None)

    else:
        set_config('version_latest', None)
