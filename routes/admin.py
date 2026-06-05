
import secrets

from flask import Blueprint, redirect, render_template, request, session, url_for
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from models import Badge, BannedIP, BannedUser, InviteCode, IPLog, Paste, User, db
from routes.helper import (
    admin_required,
    is_ip_banned,
    is_user_banned,
)

bp = Blueprint("admin", __name__)


@bp.route("/admin")
@admin_required
def admin_panel():
    return render_template("admin/admin.html")


@bp.route("/admin/assign_badge/<int:user_id>/<int:badge_id>", methods=["POST"])
@admin_required
def assign_badge(user_id, badge_id):
    user = User.query.get_or_404(user_id)
    badge = Badge.query.get_or_404(badge_id)
    if badge not in user.badges:
        user.badges.bpend(badge)
        db.session.commit()
    return redirect(url_for("users"))


@bp.route("/admin/remove_badge/<int:user_id>/<int:badge_id>", methods=["POST"])
@admin_required
def remove_badge(user_id, badge_id):
    user = User.query.get_or_404(user_id)
    badge = Badge.query.get_or_404(badge_id)
    if badge in user.badges:
        user.badges.remove(badge)
        db.session.commit()
    return redirect(url_for("users"))


@bp.route("/admin/pastes")
@admin_required
def pastes():
    search_query = request.args.get("search", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = Paste.query.order_by(Paste.published_at.desc())

    if search_query:
        query = query.filter(Paste.content.ilike(f"%{search_query}%"))

    total = query.count()
    pastes = query.offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "admin/pastes.html",
        pastes=pastes,
        page=page,
        total_pages=total_pages,
        search=search_query,
    )


@bp.route("/admin/ip_logs")
@admin_required
def ip_logs():
    search_query = request.args.get("search", "", type=str)
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = IPLog.query

    if search_query:
        query = query.filter(
            or_(
                IPLog.username.ilike(f"%{search_query}%"),
                IPLog.ip_address.ilike(f"%{search_query}%"),
            )
        )

    total = query.count()
    total_pages = (total + per_page - 1) // per_page

    logs = (
        query.order_by(IPLog.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return render_template(
        "admin/ip_logs.html",
        logs=logs,
        page=page,
        total_pages=total_pages,
        search=search_query,
    )


@bp.route("/admin/user_ip_logs/<username>")
@admin_required
def user_ip_logs(username):
    logs = (
        IPLog.query.filter_by(username=username).order_by(IPLog.timestamp.desc()).all()
    )
    return render_template("admin/user_ip_logs.html", logs=logs, username=username)


@bp.route("/admin/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method == "POST":
        user_id = int(request.form.get("_user_id"))
        badge_id = int(request.form.get("badge_id"))
        user = User.query.get_or_404(user_id)
        badge = Badge.query.get_or_404(badge_id)
        if badge not in user.badges:
            user.badges.bpend(badge)
            db.session.commit()
        return redirect(url_for("users", page=request.args.get("page", 1)))

    search_query = request.args.get("search", "", type=str)
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = User.query
    if search_query:
        query = query.filter(User.username.ilike(f"%{search_query}%"))

    total = query.count()
    total_pages = (total + per_page - 1) // per_page

    users = (
        query.order_by(User.username)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .options(joinedload(User.badges))
        .all()
    )

    users_with_ban_status = []
    for user in users:
        users_with_ban_status.append(
            {
                "user": user,
                "banned": bool(BannedUser.query.filter_by(user_id=user.id).first()),
                "badges": user.badges,
            }
        )

    badges = Badge.query.all()

    return render_template(
        "admin/users.html",
        users=users_with_ban_status,
        badges=badges,
        page=page,
        total_pages=total_pages,
        search=search_query,
    )


@bp.route("/admin/ban_ip", methods=["POST"])
@admin_required
def ban_ip():
    ip_address = request.form["ip_address"]
    reason = request.form.get("reason", "")
    if not is_ip_banned(ip_address):
        ban = BannedIP(ip_address=ip_address, reason=reason)
        db.session.add(ban)
        db.session.commit()
    return redirect(url_for("ip_logs"))


@bp.route("/admin/unban_ip/<ip_address>")
@admin_required
def unban_ip(ip_address):
    ban = BannedIP.query.filter_by(ip_address=ip_address).first()
    if ban:
        db.session.delete(ban)
        db.session.commit()
    return redirect(url_for("ip_logs"))


@bp.route("/admin/ban_user/<int:user_id>", methods=["POST"])
@admin_required
def ban_user(user_id):
    reason = request.form.get("reason", "")
    if not is_user_banned(user_id):
        ban = BannedUser(user_id=user_id, reason=reason)
        db.session.add(ban)
        db.session.commit()
    return redirect(url_for("users"))


@bp.route("/admin/unban_user/<int:user_id>")
@admin_required
def unban_user(user_id):
    ban = BannedUser.query.filter_by(user_id=user_id).first()
    if ban:
        db.session.delete(ban)
        db.session.commit()
    return redirect(url_for("users"))


@bp.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = User.query.get(user_id)
    if user:
        for paste in user.pastes:
            db.session.delete(paste)
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for("users"))


@bp.route("/admin/generate_invite", methods=["GET", "POST"])
@admin_required
def generate_invite():
    if request.method == "POST":
        code = secrets.token_hex(8)
        invite = InviteCode(code=code, creator_id=session["_user_id"])
        db.session.add(invite)
        db.session.commit()
        return render_template("admin/generated_invite.html", code=code)
    return render_template("admin/generate_invite.html")


@bp.route("/admin/invite_codes")
@admin_required
def invite_codes():
    return render_template("admin/invite_codes.html")


@bp.route("/admin/all_invite_codes")
@admin_required
def all_invite_codes():
    codes = InviteCode.query.order_by(InviteCode.created_at.desc()).all()
    return render_template("admin/all_invite_codes.html", codes=codes)


@bp.route("/admin/delete_invite_code/<int:code_id>", methods=["POST"])
@admin_required
def delete_invite_code(code_id):
    code = InviteCode.query.get_or_404(code_id)
    db.session.delete(code)
    db.session.commit()
    return redirect(url_for("all_invite_codes"))
