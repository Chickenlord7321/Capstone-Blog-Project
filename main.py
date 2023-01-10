from flask import Flask, render_template, redirect, url_for, flash, abort
from functools import wraps
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar


CURRENT_YEAR = datetime.now().strftime("%Y")


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')  # '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# initialize Gravatar
gravatar = Gravatar(app=app,
                    size=100,
                    rating="g",
                    default="mp",
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)


# Cookie to keep the user logged in across all pages.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Decorator that allows only the admin to access certain routes.
def admin_only(arg_function):
    @wraps(arg_function)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then abort with a 403 error
        if current_user.id != 1:
            return abort(status=403)
        # Else continue with the route function
        return arg_function(*args, **kwargs)
    return decorated_function


# CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    username = db.Column(db.String(50), nullable=False)

    # This will act like a list of BlogPost objects and Comment objects attached to each User.
    # It has a bidirectional one-to-many relationship with the "author" property in
    # the BlogPost class, and with the "commenter" property in the Comment class.

    # Essentially, "posts" and "author" are linked to each other, and so are "comments" and "commenter".
    posts = relationship("BlogPost", back_populates="author")
    user_comments = relationship("Comment", back_populates="commenter")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    # Create Foreign Key; "users.id" refers to the tablename of User class.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object/
    # Has a bidirectional one-to-many relationship with the "posts" property in the User class
    author = relationship("User", back_populates="posts")

    # Relationship Between BlogPost and Comment classes:
    blogpost_comments = relationship("Comment", back_populates="parent_post")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)

    # Create Relationship between Comment and User tables
    commenter_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # "user_comments" refers to the property in the User class
    commenter = relationship("User", back_populates="user_comments")

    # Create Relationship between Comment and BlogPost tables
    parent_post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    # "blogpost_comments" refers to the property in the BlogPost class
    parent_post = relationship("BlogPost", back_populates="blogpost_comments")

    text = db.Column(db.Text, nullable=False)


db.create_all()


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, year=CURRENT_YEAR)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if email already exists.
        if User.query.filter_by(email=form.email.data).first():
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for("login"))

        # If user does not already exist, add new user to User table in database
        new_user = User()
        new_user.email = form.email.data
        new_user.username = form.username.data
        new_user.password = generate_password_hash(
            password=form.password.data,
            method="pbkdf2:sha256",
            salt_length=8
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    # On GET request:
    return render_template("register.html", form=form, year=CURRENT_YEAR)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        entered_email = form.email.data
        entered_password = form.password.data

        # Find user by email.
        user = User.query.filter_by(email=entered_email).first()
        # Check if email is incorrect, i.e. if email could not be found.
        if not user:
            flash("That email does not exist")
            return redirect(url_for("login"))
        # Check if the entered password does not match the password in the database.
        elif not check_password_hash(pwhash=user.password, password=entered_password):
            flash("Password incorrect, please try again")
            return redirect(url_for("login"))
        # If both the email and password are correct, log in the user.
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))
    # On GET request:
    return render_template("login.html", form=form, year=CURRENT_YEAR)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    # When a user submits a comment:
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to log in before posting a comment")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=form.comment_text.data,
            commenter=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        flash("Comment saved")
    # on GET request:
    return render_template("post.html", post=requested_post, form=form, year=CURRENT_YEAR)


@app.route("/about")
def about():
    return render_template("about.html", year=CURRENT_YEAR)


@app.route("/contact")
def contact():
    return render_template("contact.html", year=CURRENT_YEAR)


@admin_only
@app.route("/new-post", methods=["GET", "POST"])
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    # On GET request:
    return render_template("make-post.html", form=form, year=CURRENT_YEAR)


@admin_only
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )

    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    # On GET request:
    return render_template("make-post.html", form=edit_form, year=CURRENT_YEAR)


@admin_only
@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
