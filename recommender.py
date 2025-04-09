import pandas as pd
import os

RECOMMENDER_DATA_PATH = "Data/play_data.xlsx"
RECOMMENDER_CACHE_PATH = "recommender_cache.pkl"
RECOMMENDER_MIN_ROWS = 1000  # Auto-trigger when file has >= this many rows


# 🔁 Recommender logic
def generate_recommendations():
    df = pd.read_excel(RECOMMENDER_DATA_PATH)

    non_play_pass = df[df["Play Pass User"] == "No"]
    recommendations = []

    for user_id, user_df in non_play_pass.groupby("ID"):
        total_spent = (
            user_df["Amount Spent on In-App Purchases"].sum()
            + user_df["App/Game Price"].sum()
        )
        avg_sessions = user_df["Session Count"].mean()
        categories_used = user_df["Category"].nunique()

        # ⛔ Skip users with no meaningful activity
        if total_spent == 0 and avg_sessions <= 3:
            continue

        # 📊 Determine user segment & reason
        if total_spent > 5:
            reason = f"Spent ${total_spent:.2f}. Play Pass could cut your monthly cost."
        elif total_spent == 0 and avg_sessions > 5:
            reason = "High usage with free apps. Play Pass unlocks premium without ads."
        elif 1 < total_spent <= 5 and avg_sessions > 2:
            reason = (
                "Engaged + starting to spend. Play Pass is a smarter deal early on."
            )
        elif categories_used > 3:
            reason = (
                "You explore many app types. Play Pass gives you freedom to try more."
            )
        else:
            continue  # Skip quiet users

        # 🔍 Pick relevant top-rated paid apps
        top_category = user_df["Category"].mode()[0]
        paid_apps = (
            df[
                (df["Category"] == top_category)
                & (df["Free/Paid"] == "Paid")
                & (df["Rating"] >= 4.0)
            ][["App Name", "Category", "Rating"]]
            .drop_duplicates()
            .head(3)
        )

        for _, row in paid_apps.iterrows():
            recommendations.append(
                {
                    "User ID": user_id,
                    "Recommended App": row["App Name"],
                    "Category": row["Category"],
                    "Rating": row["Rating"],
                    "Why Play Pass?": reason,
                }
            )
    recs_df = pd.DataFrame(recommendations)
    recs_df["Suggested Offers"] = recs_df["Why Play Pass?"].apply(suggest_offers)

    recs_df.attrs["row_count"] = df.shape[0]
    recs_df.to_pickle(RECOMMENDER_CACHE_PATH)
    return recs_df


def suggest_offers(reason):
    reason = reason.lower()

    if any(keyword in reason for keyword in ["spent", "cost", "save", "smarter deal"]):
        return [
            "🎁 30-day free Play Pass trial",
            "💸 10% off next in-app purchase",
            "📦 Bundle top 3 paid apps",
        ]
    elif any(keyword in reason for keyword in ["usage", "premium", "ads", "unlock"]):
        return [
            "🚫 Ad-free version unlock",
            "🎮 Free premium game gift",
            "📲 Early access to top games",
        ]
    elif "explore" in reason or "freedom" in reason:
        return [
            "🔍 Discovery pack trial",
            "🆓 Weekly app rotation",
            "🎉 1-month Play Pass at 50%",
        ]
    else:
        return ["💡 Suggest manually"]


# Add this to each row in recs_df


# ✅ Check if new rows should auto-trigger the model
def should_trigger_recommender():
    try:
        df = pd.read_excel(RECOMMENDER_DATA_PATH)
        new_count = df.shape[0]

        if os.path.exists(RECOMMENDER_CACHE_PATH):
            cached = pd.read_pickle(RECOMMENDER_CACHE_PATH)
            old_count = cached.attrs.get("row_count", 0)
        else:
            old_count = 0

        return (new_count - old_count) >= RECOMMENDER_MIN_ROWS
    except Exception as e:
        print("Error checking for trigger:", e)
        return False


# ✅ Get cached recommendations
def get_cached_recommendations():
    if os.path.exists(RECOMMENDER_CACHE_PATH):
        return pd.read_pickle(RECOMMENDER_CACHE_PATH)
    return pd.DataFrame()
