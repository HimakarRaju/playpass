import random
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import pandas as pd
import os
import plotly.express as px
import plotly.io as pio
import json
import logging
from datetime import datetime
from recommender import (
    generate_recommendations,
    should_trigger_recommender,
    get_cached_recommendations,
    RECOMMENDER_CACHE_PATH,
)

app = Flask(__name__)
app.secret_key = "your_secret_key_here"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///play_members.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"

db = SQLAlchemy(app)

DATA_FILE = "Data/play_data.xlsx"
dataset_cache = {"df": None}

EXPECTED_COLUMNS = [
    "ID",
    "Name",
    "Email",
    "Phone",
    "Age",
    "Gender",
    "Income Level",
    "Device Type",
    "Android Version",
    "App Name",
    "Developer",
    "Category",
    "Sub_Category",
    "Free/Paid",
    "In-App Purchases",
    "App Size (MB)",
    "Total Installs",
    "Transaction ID",
    "Transaction Type",
    "App/Game Price",
    "Discount Applied",
    "Promo Code Used",
    "Price Paid (with Coupon)",
    "Amount Spent on In-App Purchases",
    "Time Spent (min)",
    "Session Count",
    "Time Since Last Use (days)",
    "Favorite Flag",
    "Uninstalled",
    "Date",
    "Time",
    "Day of Week",
    "Weekend",
    "Season",
    "Rating",
    "Review Text",
    "Review Sentiment",
    "Review Length",
    "Demographic Location",
    "State",
    "Country",
    "Region",
    "Play Pass Plan",
    "Play Pass User",
    "Subscription Duration",
    "Auto-Renew",
    "App Tags",
    "Age Rating",
    "Device Locale/Language",
]

# Dummy colors for visualization
COLOR_MAP = {
    "User": "#4F46E5",
    "App": "#10B981",
    "Category": "#F59E0B",
    "Offer": "#EF4444",
    "Cluster": "#6366F1",
}


class PlayMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(255))


def save_charts_to_disk(charts, filepath="chart_cache.json"):
    with open(filepath, "w") as f:
        json.dump(charts, f)


def load_charts_from_disk(filepath="chart_cache.json"):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return None


# Global dataset cache with lock for thread safety
from threading import Lock

dataset_cache = {"df": None, "lock": Lock()}


def load_dataset():
    with dataset_cache["lock"]:
        try:
            if dataset_cache["df"] is not None:
                return True  # Already loaded

            print("Loading dataset...")
            df = pd.read_excel(DATA_FILE)

            # Clean column names
            df.columns = [col.strip() for col in df.columns]

            print(f"Loaded dataset with {df.shape[0]} rows and {df.shape[1]} columns.")
            if df.empty:
                raise ValueError("Dataset is empty.")

            # Validate and reorder columns
            if set(df.columns) != set(EXPECTED_COLUMNS):
                missing = set(EXPECTED_COLUMNS) - set(df.columns)
                extra = set(df.columns) - set(EXPECTED_COLUMNS)
                raise ValueError(
                    f"Dataset structure mismatch. Missing: {missing}, Extra: {extra}"
                )

            df = df[EXPECTED_COLUMNS]  # Reorder to expected
            df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
            dataset_cache["df"] = df
            app.logger.info("Dataset loaded and cached successfully.")
            return True

        except Exception as e:
            app.logger.error(f"Failed to load dataset: {str(e)}")
            dataset_cache["df"] = None
            return False


def get_dataset():
    with dataset_cache["lock"]:
        if dataset_cache["df"] is None:
            if not load_dataset():
                raise RuntimeError("Failed to load dataset.")
        return dataset_cache[
            "df"
        ].copy()  # Return a copy to prevent accidental modification


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Login required", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


@app.route("/get-data")
def get_chart_meta():
    try:
        # Only send chart-relevant metadata
        df = dataset_cache["df"]
        sample = df.sample(n=1).dropna(axis=1)  # grab sample row with non-null columns
        columns = sample.columns.tolist()

        summary = {
            "columns": columns,
        }
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/data")
def api_data():
    if dataset_cache.get("df") is None:
        if not load_dataset():
            return jsonify({"error": "Failed to load dataset"}), 500

    df = dataset_cache["df"]

    # Get pagination params
    start = int(request.args.get("start", 0))
    length = int(request.args.get("length", 100))

    # Slice the DataFrame
    page = df.iloc[start : start + length]

    # Sanitize for JSON
    page = page.replace({np.nan: None, np.inf: None, -np.inf: None})
    data = page.to_dict(orient="records")

    return jsonify({"data": data, "recordsTotal": len(df), "recordsFiltered": len(df)})


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/refresh_data", methods=["POST"])
@login_required
def refresh_data():
    success = load_dataset()
    if success:
        return jsonify({"status": "success", "message": "Data refreshed!"})
    return jsonify({"status": "error", "message": "Failed to refresh dataset."})


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        if PlayMember.query.filter_by(username=username).first():
            flash("Username already exists", "danger")
            return redirect(url_for("register"))

        new_user = PlayMember(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("User registered!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = PlayMember.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            load_dataset()
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    df = get_dataset()
    if df is None:
        load_dataset()
        df = dataset_cache["df"]

    summary = {
        "total_users": df["ID"].nunique(),
        "total_revenue": round(df["Price Paid (with Coupon)"].sum(), 2),
        "avg_session": round(df["Time Spent (min)"].mean(), 2),
        "active_regions": df["Region"].nunique(),
        # get count of recommendations
        "total_recommendations": len(get_cached_recommendations()),
    }

    category_list = sorted(df["Category"].dropna().unique().tolist())
    region_list = sorted(df["Region"].dropna().unique().tolist())

    return render_template(
        "dashboard.html",
        summary=summary,
        category_list=category_list,
        region_list=region_list,
        data=df.to_dict(orient="records"),
    )


@app.route("/get_charts", methods=["GET"])
@login_required
def get_charts():
    if request.args.get("refresh") != "true":
        cached = load_charts_from_disk()
        if cached:
            return jsonify(cached)

    try:
        df = dataset_cache.get("df")
        if df is None:
            load_dataset()
            df = dataset_cache["df"]
        if list(df.columns) != EXPECTED_COLUMNS:
            return jsonify({"error": "Dataset structure mismatch"})

        cat_data = df["Category"].value_counts().nlargest(10).reset_index()
        cat_data.columns = ["Category", "count"]

        cat_fig = px.bar(cat_data, x="Category", y="count", title="Top 10 Categories")
        play_fig = px.pie(df, names="Play Pass User", title="Play Pass Breakdown")
        inapp_fig = px.bar(
            df.groupby("Category")["Amount Spent on In-App Purchases"]
            .mean()
            .reset_index(),
            x="Category",
            y="Amount Spent on In-App Purchases",
            title="Avg In-App Purchase",
        )
        rating_fig = px.histogram(df, x="Rating", title="Ratings")

        charts = {
            "cat_chart": pio.to_json(cat_fig),
            "play_chart": pio.to_json(play_fig),
            "inapp_chart": pio.to_json(inapp_fig),
            "rating_chart": pio.to_json(rating_fig),
        }

        save_charts_to_disk(charts)
        return jsonify(charts)

    except Exception as e:
        import traceback

        print(traceback.format_exc())
        return jsonify({"error": str(e)})


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if not file:
        flash("No file uploaded", "warning")
        return redirect(url_for("dashboard"))

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        df = pd.read_excel(filepath)
        if list(df.columns) != EXPECTED_COLUMNS:
            dataset_cache["df"] = df
            flash("Uploaded file structure doesn't match expected dataset.", "danger")
        else:
            df.to_excel(DATA_FILE, index=False)
            flash("Dataset updated!", "success")
    except Exception as e:
        flash(f"Error processing file: {e}", "danger")

    return redirect(url_for("dashboard"))


@app.route("/run_recommender", methods=["POST"])
@login_required
def run_recommender():
    try:
        recs_df = generate_recommendations()
        recs_df.attrs["row_count"] = pd.read_excel(DATA_FILE).shape[0]
        recs_df.to_pickle(RECOMMENDER_CACHE_PATH)
        return jsonify(
            {
                "status": "success",
                "message": f"{len(recs_df)} recommendations generated.",
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/recommendations")
@login_required
def recommendations():
    try:
        recs = get_cached_recommendations()
        if recs.empty:
            flash(
                "No recommendations available. Please generate recommendations first.",
                "warning",
            )
            return render_template("recommendations.html", recommendations=[])

        # Make sure all required columns exist for recommendations
        required_columns = ["User ID", "Recommended App", "Category", "Why Play Pass?"]
        if not all(col in recs.columns for col in required_columns):
            missing = [col for col in required_columns if col not in recs.columns]
            flash(f"Missing required columns: {', '.join(missing)}", "error")
            return render_template("recommendations.html", recommendations=[])

        # Convert recommendations to dict for template
        recommendations = recs.to_dict(orient="records")

        # Calculate visualization data with error handling
        full_df = get_dataset()
        visualization_data = {}

        # Age data calculation
        try:
            if "Age Group" in full_df.columns:
                age_data = full_df["Age Group"].value_counts().sort_index().to_dict()
            else:
                # Create age groups if only 'Age' column exists
                if "Age" in full_df.columns:
                    full_df["Age Group"] = pd.cut(
                        full_df["Age"],
                        bins=[0, 18, 25, 35, 50, 100],
                        labels=["0-18", "19-25", "26-35", "36-50", "50+"],
                    )
                    age_data = (
                        full_df["Age Group"].value_counts().sort_index().to_dict()
                    )
                else:
                    age_data = {"0-18": 0, "19-25": 0, "26-35": 0, "36-50": 0, "50+": 0}
        except Exception as e:
            app.logger.error(f"Error calculating age data: {str(e)}")
            age_data = {"0-18": 0, "19-25": 0, "26-35": 0, "36-50": 0, "50+": 0}

        # Region data calculation
        try:
            region_data = (
                full_df["Region"].value_counts().nlargest(10).to_dict()
                if "Region" in full_df.columns
                else {"North": 0, "South": 0, "East": 0, "West": 0}
            )
        except Exception as e:
            app.logger.error(f"Error calculating region data: {str(e)}")
            region_data = {"North": 0, "South": 0, "East": 0, "West": 0}

        # Category data calculation
        try:
            category_data = (
                full_df["Category"].value_counts().nlargest(10).to_dict()
                if "Category" in full_df.columns
                else {"Games": 0, "Productivity": 0, "Entertainment": 0}
            )
        except Exception as e:
            app.logger.error(f"Error calculating category data: {str(e)}")
            category_data = {"Error": 0}

        # Render template with data
        return render_template(
            "recommendations.html",
            recommendations=recommendations,
            age_data=age_data,
            region_data=region_data, 
            category_data=category_data,
            total_records=len(recommendations)
        )
    except Exception as e:
        app.logger.error(f"Error in recommendations route: {str(e)}")
        flash("Error loading recommendations.", "error")
        return render_template(
            "recommendations.html",
            recommendations=[],
            age_data={},
            region_data={},
            category_data={},
            total_records=0,
        )


@app.route("/send_offer", methods=["POST"])
def send_offer():
    user_id = request.form.get("user_id")
    custom_offer = request.form.get("custom_offer")

    # 📌 You can store it in a DB or file — for now, just print/log it
    print(f"Offer sent to User {user_id}: {custom_offer}")

    flash(f"Offer sent to User {user_id}!", "success")
    return redirect(url_for("merchant_panel"))


@app.route("/graph")
@login_required
def graph_visualization():
    return render_template("graph_visualization.html")


@app.route("/api/graph_data")
@login_required
def graph_data():
    import networkx as nx
    import pickle

    # Load full dataset
    df = dataset_cache.get("df")
    if df is None:
        load_dataset()
        df = dataset_cache["df"]

    # Load recommendations
    try:
        with open("recommender_cache.pkl", "rb") as f:
            recs = pickle.load(f)
    except FileNotFoundError:
        return jsonify({"error": "Recommendation cache not found"}), 500

    # Build Knowledge Graph
    G = nx.Graph()

    for _, row in recs.iterrows():
        user = f"user_{row['User ID']}"
        app = f"app_{row['Recommended App']}"
        category = f"cat_{row['Category']}"
        reason = f"reason_{row['Why Play Pass?']}"

        G.add_node(user, type="user")
        G.add_node(app, type="app")
        G.add_node(category, type="category")
        G.add_node(reason, type="reason")

        G.add_edge(user, app)
        G.add_edge(app, category)
        G.add_edge(app, reason)

    # Create mapping of user IDs to names from the dataset
    user_names = {}
    for _, row in df.iterrows():
        user_id = f"user_{row['ID']}"
        user_names[user_id] = row.get("Name", f"User {row['ID']}")

    nodes = []
    for n in G.nodes:
        node_data = {"id": n, "type": G.nodes[n]["type"]}
        if n.startswith("user_") and n in user_names:
            node_data["name"] = user_names[n]
        nodes.append(node_data)

    edges = [{"source": u, "target": v} for u, v in G.edges]

    # Optimized graph data generation
    try:
        # Combine duplicate nodes and edges
        unique_nodes = {}
        for node in nodes:
            unique_nodes[node["id"]] = node

        # Combine duplicate edges
        unique_edges = {}
        for edge in edges:
            key = f"{edge['source']}-{edge['target']}"
            unique_edges[key] = edge

        # Simplify user groups structure
        optimized_user_groups = {}
        for _, row in recs.iterrows():
            user_id = f"user_{row['User ID']}"
            offers = row["Suggested Offers"]
            offers = [offers] if not isinstance(offers, (list, np.ndarray)) else offers

            for offer in offers:
                if pd.notna(offer):
                    offer_str = str(offer).strip()
                    if offer_str not in optimized_user_groups:
                        optimized_user_groups[offer_str] = set()
                    optimized_user_groups[offer_str].add(user_id)

        # Convert sets to lists for JSON serialization
        user_groups = {k: list(v) for k, v in optimized_user_groups.items()}

        # Return optimized response
        return jsonify(
            {
                "graph": {
                    "nodes": list(unique_nodes.values()),
                    "edges": list(unique_edges.values()),
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                },
                "user_groups": user_groups,
                "status": "success",
            }
        )

    except Exception as e:
        app.logger.error(f"Error generating optimized graph data: {str(e)}")
        return (
            jsonify(
                {"error": "Failed to generate optimized graph data", "details": str(e)}
            ),
            500,
        )


recommendations_df = get_cached_recommendations()


def generate_user_app_graph():
    nodes = []
    edges = []
    seen_users = set()
    seen_apps = set()

    for _, row in recommendations_df.iterrows():
        uid = str(row["User ID"])
        app = row["Recommended App"]

        if uid not in seen_users:
            nodes.append(
                {
                    "data": {"id": f"user_{uid}", "label": uid, "type": "User"},
                    "classes": "user",
                }
            )
            seen_users.add(uid)

        if app not in seen_apps:
            nodes.append(
                {
                    "data": {"id": f"app_{app}", "label": app, "type": "App"},
                    "classes": "app",
                }
            )
            seen_apps.add(app)

        edges.append({"data": {"source": f"user_{uid}", "target": f"app_{app}"}})

    return nodes, edges


def generate_app_category_graph():
    nodes = []
    edges = []
    seen_apps = set()
    seen_categories = set()

    for _, row in recommendations_df.iterrows():
        app = row["Recommended App"]
        category = row["Category"]

        if app not in seen_apps:
            nodes.append(
                {
                    "data": {"id": f"app_{app}", "label": app, "type": "App"},
                    "classes": "app",
                }
            )
            seen_apps.add(app)

        if category not in seen_categories:
            nodes.append(
                {
                    "data": {
                        "id": f"cat_{category}",
                        "label": category,
                        "type": "Category",
                    },
                    "classes": "category",
                }
            )
            seen_categories.add(category)

        edges.append({"data": {"source": f"app_{app}", "target": f"cat_{category}"}})

    return nodes, edges


def generate_app_offer_graph():
    nodes = []
    edges = []
    seen_apps = set()
    seen_offers = set()

    for _, row in recommendations_df.iterrows():
        app = row["Recommended App"]
        offer = row["Suggested Offers"]

        if app not in seen_apps:
            nodes.append(
                {
                    "data": {"id": f"app_{app}", "label": app, "type": "App"},
                    "classes": "app",
                }
            )
            seen_apps.add(app)

        if offer not in seen_offers:
            nodes.append(
                {
                    "data": {"id": f"offer_{offer}", "label": offer, "type": "Offer"},
                    "classes": "offer",
                }
            )
            seen_offers.add(offer)

        edges.append({"data": {"source": f"app_{app}", "target": f"offer_{offer}"}})

    return nodes, edges


def generate_user_offer_graph():
    nodes = []
    edges = []
    seen_users = set()
    seen_offers = set()

    for _, row in recommendations_df.iterrows():
        uid = str(row["User ID"])
        offer = row["Suggested Offers"]

        if uid not in seen_users:
            nodes.append(
                {
                    "data": {"id": f"user_{uid}", "label": uid, "type": "User"},
                    "classes": "user",
                }
            )
            seen_users.add(uid)

        if offer not in seen_offers:
            nodes.append(
                {
                    "data": {"id": f"offer_{offer}", "label": offer, "type": "Offer"},
                    "classes": "offer",
                }
            )
            seen_offers.add(offer)

        edges.append({"data": {"source": f"user_{uid}", "target": f"offer_{offer}"}})

    return nodes, edges


def generate_user_cluster_graph():
    # Simulated clusters for demo; in real case use ML or clustering logic
    nodes = []
    edges = []
    seen_users = set()
    num_clusters = 5
    cluster_ids = [f"Cluster {i+1}" for i in range(num_clusters)]

    for cluster in cluster_ids:
        nodes.append(
            {
                "data": {
                    "id": f"cluster_{cluster}",
                    "label": cluster,
                    "type": "Cluster",
                },
                "classes": "cluster",
            }
        )

    for _, row in recommendations_df.iterrows():
        uid = str(row["User ID"])
        cluster = random.choice(cluster_ids)

        if uid not in seen_users:
            nodes.append(
                {
                    "data": {"id": f"user_{uid}", "label": uid, "type": "User"},
                    "classes": "user",
                }
            )
            seen_users.add(uid)

        edges.append(
            {"data": {"source": f"user_{uid}", "target": f"cluster_{cluster}"}}
        )

    return nodes, edges


@app.route("/merchant-panel")
def merchant_panel():
    recs = get_cached_recommendations()
    if recs.empty:
        return render_template("merchant_panel.html", recommendations=[], loaded=False)

    recs = recs.to_dict(orient="records")  # List of dicts
    return render_template("merchant_panel.html", recommendations=recs, loaded=True)


@app.route("/submit_merchant_action", methods=["POST"])
def submit_merchant_action():
    data = request.get_json()
    offer = data.get("offer")
    notes = data.get("notes")
    selected = data.get("selected")

    app.logger.info(
        f"[{datetime.now()}] Offer: {offer} | Notes: {notes} | Affected Rows: {len(selected)}"
    )

    with open("merchant_actions_log.csv", "a", encoding="utf-8") as f:
        for row in selected:
            row_data = ",".join(row).replace("\n", " ").strip()
            f.write(f'"{datetime.now()}","{offer}","{notes}","{row_data}"\n')

    return jsonify({"status": "success"})


@app.route("/api/recommendations", methods=["POST"])
@login_required
def get_recommendations_data():
    try:
        # Get DataTables parameters
        start = request.json.get("start", 0)
        length = request.json.get("length", 25)
        filters = request.json.get("filters", {})

        # Get recommendations
        recs = get_cached_recommendations()

        # Apply filters
        if filters.get("region"):
            recs = recs[recs["Region"] == filters["region"]]
        if filters.get("age"):
            recs = recs[recs["Age Group"] == filters["age"]]
        if filters.get("category"):
            recs = recs[recs["Category"] == filters["category"]]

        # Calculate total records
        total_records = len(recs)

        # Paginate
        paginated_recs = recs.iloc[start : start + length]

        return jsonify(
            {
                "data": paginated_recs.to_dict("records"),
                "recordsTotal": total_records,
                "recordsFiltered": total_records,
            }
        )

    except Exception as e:
        app.logger.error(f"Error in recommendations API: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    with app.app_context():
        db.create_all()
    app.run(debug=True)
