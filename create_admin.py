from app import app
from models import db, User

with app.app_context():
    user = User(username="donnie", privacy_policy=1, is_admin=True)
    user.set_password("PixieCat79")

    db.session.add(user)
    db.session.commit()


