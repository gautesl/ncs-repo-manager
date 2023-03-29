from flask import Flask, render_template, request, url_for, flash, redirect, g, session
from github import GithubException
from flask_github import GitHub, GitHubError
from typing import Tuple, List, Dict
from repo_manager import RepoManager, REPOSITORIES, Access
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["BROWSER_SESSION_SECRET_KEY"]
app.config["GITHUB_CLIENT_ID"] = os.environ["GITHUB_AUTHENTICATION_CLIENT_ID"]
app.config["GITHUB_CLIENT_SECRET"] = os.environ["GITHUB_AUTHENTICATION_CLIENT_SECRET"]

github = GitHub(app)

users = {}

# Utilify functions
def create_table(mapping : Dict[str, Dict[str, Access]]) -> Tuple[List[str], List[List[str]]]:
    repos = [repo.split("/")[1] for repo in REPOSITORIES]
    head = [""] + repos
    rows = []

    for user, access_map in mapping.items():
        if not access_map:
            flash(f"Could not find GitHub user '{user}'")
            continue
        row = [user] + [str(access_map[repo]) for repo in repos]
        rows.append(row)
    return head, rows

# Flask functions

@app.before_request
def load_user():
    g.user = None
    g.logged_in = False
    if "user_id" in session:
        id = session["user_id"]
        if id in users:
            g.user = users[id]
            g.logged_in = bool("manager" in g.user)


# @app.route("/login")
# def login():
#     next_url = url_for("home")
#     oauth_token = os.environ["ACCESS_TOKEN"]
#     try:
#         github_user = github.get("/user", access_token=oauth_token)
#     except GitHubError:
#         flash("Insufficient access.")
#         next_url = url_for("insufficient_access")
#         return redirect(next_url)

#     id = github_user["id"]
#     users[id] = {}
#     users[id]["login"] = github_user["login"]
#     users[id]["access_token"] = oauth_token

#     session["user_id"] = id

#     try:
#         manager = RepoManager(oauth_token, id)
#         users[id]["manager"] = manager
#     except GithubException:
#         next_url = url_for("insufficient_access")

#     return redirect(next_url)


@app.route("/login")
def login():
    return github.authorize(scope="repo,admin:org")


@app.route("/github-callback")
@github.authorized_handler
def authorized(oauth_token):
    next_url = request.args.get("next") or url_for("home")
    if oauth_token is None:
        flash("Authorization failed.")
        return redirect(next_url)

    try:
        github_user = github.get("/user", access_token=oauth_token)
    except GitHubError:
        flash("Insufficient access.")
        next_url = url_for("insufficient_access")
        return redirect(next_url)

    id = github_user["id"]
    users[id] = {}
    users[id]["login"] = github_user["login"]
    users[id]["access_token"] = oauth_token

    session["user_id"] = id

    print("Authenticated user with id", id, "login", github_user["login"])
    try:
        manager = RepoManager(oauth_token, id)
        users[id]["manager"] = manager
    except GithubException:
        next_url = url_for("insufficient_access")

    return redirect(next_url)


@github.access_token_getter
def token_getter():
    user = g.user
    if user and "access_token" in user:
        return user["access_token"]


@app.route("/")
def home():
    return render_template("home.html", logged_in=g.logged_in, repos=REPOSITORIES)


@app.route("/insufficient_access/")
def about():
    return render_template("insufficient_access.html")


@app.route("/check_users/", methods=("GET", "POST"))
def check_users():
    head = None
    rows = None
    available = -1

    if g.logged_in:
        available = g.user["manager"].get_available_requests()

    if request.method == "POST":
        usernames = request.form["usernames"]
        if not usernames:
            flash("At least one username is required")
        elif not g.logged_in:
            flash("You must be logged in to use this functionality")
        else:
            g.user["manager"].clear_cache()
            res = g.user["manager"].list_users(usernames.split())
            head, rows = create_table(res)
            available = g.user["manager"].get_available_requests()

    return render_template(
        "check_users.html", logged_in=g.logged_in, head=head, rows=rows, available=available
    )

@app.route("/add_users/", methods=("GET", "POST"))
def add_users():
    available = -1

    if g.logged_in:
        available = g.user["manager"].get_available_requests()

    if request.method == "POST":
        usernames = request.form["usernames"]
        if not usernames:
            flash("At least one username is required")
        elif not g.logged_in:
            flash("You must be logged in to use this functionality")
        else:
            res = g.user["manager"].add_users(usernames.split())
            for username, (success, message) in res.items():
                if success and message:
                    flash(f"Partial success for {username}: {message}")
                elif message:
                    flash(f"Failed to add {username}: {message}")
                elif success:
                    flash(f"Added user {username}", category="success")
            g.user["manager"].clear_cache()
            
            return redirect(url_for("check_users"))

    return render_template("add_users.html", logged_in=g.logged_in, available=available)

@app.route("/list_users/", methods=("GET", "POST"))
def list_users():
    head = None
    rows = None
    available = -1

    if g.logged_in:
        available = g.user["manager"].get_available_requests()

    if request.method == "POST":
        if not g.logged_in:
            flash("You must be logged in to use this functionality")
        else:
            g.user["manager"].clear_cache()
            res = g.user["manager"].list_outside_collaborators()
            head, rows = create_table(res)
            available = g.user["manager"].get_available_requests()

    return render_template(
        "list_users.html", logged_in=g.logged_in, head=head, rows=rows, available=available
    )
