import os
import re
from functools import lru_cache
import sys

import dotenv
import requests
from flask import Flask, abort, redirect, render_template, request
from flask_cors import CORS

dotenv.load_dotenv()

ITCHIO_API_KEY = os.getenv("ITCHIO_API_KEY")

app = Flask(__name__)
cors = CORS(app, resources={r"/*": {"origins": "*"}}, origins="*", allow_headers="*")

providers = {}


def register_provider(name: str):
    def decorator(func):
        providers[name] = func
        return func

    return decorator


@register_provider("itch")
class Itch:
    @lru_cache(512)
    @staticmethod
    def id_from_name(name: str):
        response = requests.get(f"https://{name}.itch.io", timeout=10)
        # begin = response.raw.read(500, True).decode("utf-8")
        # response.close()
        if response.status_code == 200:
            rs = re.search(r'content="users/(\d+)"', response.text)
            if rs is None:
                return None
            return "itch:" + rs.group(1)
        return None

    @lru_cache(512)
    @staticmethod
    def get_details(id: int):
        response = requests.get(
            f"https://itch.io/api/1/{ITCHIO_API_KEY}/users/{id}", timeout=10
        )
        resp_json = response.json()
        if response.status_code == 200 and "user" in resp_json:
            return {
                "user_id": "itch:" + str(id),
                "user_name": "itch:"
                + resp_json["user"]["url"]
                .removeprefix("https://")
                .removesuffix(".itch.io"),
                "display_name": resp_json["user"]["username"],
                "skin": None,
            }
        return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search():
    query = request.args.get("q")

    if not query:
        return redirect("/")

    query = re.sub(r"[^a-zA-Z0-9:]", "", query)

    if ":" not in query:
        query = f"itch:{query}"

    if query.count(":") > 1:
        return abort(404)

    provider, identifier = query.split(":")

    if provider not in providers:
        return abort(404)

    if not identifier:
        return abort(404)

    if identifier.isdigit():
        return redirect(f"/player/{provider}:{identifier}")
    else:
        user_id = providers[provider].id_from_name(identifier)

        if user_id is None:
            return abort(404)

        return redirect(f"/player/{user_id}")


@app.route("/player/<string:provider>:<int:user_id>")
def player_profile(provider: str, user_id: int):
    if provider not in providers:
        print("PP NoProv")
        return abort(404)

    profile = providers[provider].get_details(user_id)
    if profile is None:
        print("PP NoID")
        return abort(404)

    return render_template("player.html", profile=profile)


@app.route("/player/<string:provider>:<string:username>")
def player_profile_by_name(provider: str, username: int):
    if provider not in providers:
        print("PN NoProv")
        return abort(404)

    user_id = providers[provider].id_from_name(username)
    if user_id is None:
        print("PN NoID")
        return abort(404)

    return redirect(f"/player/{user_id}")


@app.route("/api/1/id_of/<string:fullname>")
def get_id(fullname: str):
    if fullname.count(":") != 1:
        return {"success": False, "user_id": None, "message": "Invalid name"}

    provider, name = fullname.split(":")
    if provider not in providers:
        return {"success": False, "user_id": None, "message": "Provider not found"}

    user_id = providers[provider].id_from_name(name)
    if user_id is None:
        return {"success": False, "user_id": None, "message": "User not found"}

    return {"success": True, "user_id": user_id}


@app.route("/api/1/player/<string:fullid>")
def get_details(fullid: str):
    if fullid.count(":") != 1:
        return {"success": False, "profile": None, "message": "Invalid ID"}

    provider, user_id = fullid.split(":")
    if provider not in providers:
        return {"success": False, "profile": None, "message": "Provider not found"}

    user_id = providers[provider].get_details(user_id)
    if user_id is None:
        return {"success": False, "profile": None, "message": "User not found"}

    return {"success": True, "profile": user_id}


if __name__ == "__main__":
    app.run(port=int(sys.argv[-1]))
