import re
from functools import wraps

import bleach
from bleach.css_sanitizer import CSSSanitizer
from flask import (
    Blueprint,
    abort,
    g,
    redirect,
    request,
    session,
    url_for,
)

from models import BannedIP, BannedUser, IPLog, User, db
from properties import (
    ALLOWED_CSS_PROPERTIES,
    CURRENT_POLICY_VERSION,
    allowed_attributes,
    allowed_tags,
)

bp = Blueprint("helper", __name__)


def sanitize_css(css):
    css = re.sub(r"@import[^;]*;", "", css, flags=re.IGNORECASE)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    declarations = css.split(";")
    sanitized_declarations = []

    for decl in declarations:
        decl = decl.strip()
        if not decl:
            continue
        if ":" not in decl:
            continue
        prop, value = decl.split(":", 1)
        prop = prop.strip().lower()
        value = value.strip()

        if re.search(r"expression|url\(", value, re.IGNORECASE):
            if prop == "background-image":
                pass
            else:
                continue

        if prop in ALLOWED_CSS_PROPERTIES:
            sanitized_declarations.append(f"{prop}: {value}")

    return "; ".join(sanitized_declarations)


class NoImportCSSSanitizer(CSSSanitizer):
    def sanitize_css_import(self, css):
        css = re.sub(r"@import[^;]*;", "", css, flags=re.IGNORECASE)
        return super().sanitize_css(css)


css_sanitizer_instance = NoImportCSSSanitizer(
    allowed_css_properties=ALLOWED_CSS_PROPERTIES
)
css_sanitizer_instance = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)


def extract_css_declarations(css_block):
    match = re.search(r"\{([^}]*)\}", css_block, re.DOTALL)
    if match:
        return match.group(1)
    return css_block


def sanitize_content(content):
    return bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        css_sanitizer=css_sanitizer_instance,
        strip=True,
    )


def is_ip_banned(ip):
    return BannedIP.query.filter_by(ip_address=ip).first() is not None


def is_user_banned(user_id):
    return BannedUser.query.filter_by(user_id=user_id).first() is not None


def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0].split(",")[0]
    else:
        ip = request.remote_addr
    return ip


def log_ip(action):
    user_id = session.get("user_id")
    if not user_id:
        return

    user = User.query.get(user_id)
    if not user:
        return

    ip = get_client_ip()
    ip_log = IPLog(username=user.username, ip_address=ip, action=action)
    db.session.add(ip_log)
    db.session.commit()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "_user_id" not in session:
            return redirect(url_for("user.login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = User.query.get(session.get("_user_id"))
        if not user or not user.is_admin:
            abort(403)  # FORBIDDEEN
        return f(*args, **kwargs)

    return decorated_function


def get_form_value(key):
    value = request.form.get(key)
    return value if value is not None else ""


@bp.context_processor
def utility_processor():
    def is_ip_banned(ip):
        return BannedIP.query.filter_by(ip_address=ip).first() is not None

    def sanitize_content_for_template(content):
        return sanitize_content(content)

    return dict(
        is_ip_banned=is_ip_banned, sanitize_content=sanitize_content_for_template
    )


def get_total_pages(total_items, items_per_page):
    return (total_items + items_per_page - 1) // items_per_page


@bp.before_request
def load_user():
    g.current_user = None
    if "_user_id" in session:
        g.current_user = User.query.get(session["_user_id"])


@bp.before_request
def check_privacy_policy():
    if "_user_id" in session:
        user = User.query.get(session["_user_id"])
        if user and user.privacy_policy != CURRENT_POLICY_VERSION:
            if request.endpoint != "accept_terms":
                return redirect(url_for("accept_terms"))


@bp.context_processor
def inject_user():
    current_user = getattr(g, "current_user", None)
    return dict(current_user=current_user)
