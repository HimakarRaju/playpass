# python to read a pickel file
import pandas as pd
import os

RECOMMENDER_CACHE_PATH = "recommender_cache.pkl"

def get_cached_recommendations():
    try:
        if os.path.exists(RECOMMENDER_CACHE_PATH):
            return pd.read_pickle(RECOMMENDER_CACHE_PATH)
        else:
            return None
    except Exception as e:
        print("Error reading cache:", e)
        return None

recs_df = get_cached_recommendations()
if recs_df is not None: 
    print("Cached recommendations loaded successfully.")
    print(recs_df.head())  # Display the first few rows of the DataFrame
else:
    print("No cached recommendations found or error occurred.")


import pandas as pd

df = pd.read_excel("Data/play_data.xlsx")
print("Total Rows:", df.shape[0])
print("Columns:", df.columns.tolist())
print("Sample Rows:\n", df.head())

non_play_pass = df[df["Play Pass User"] == "No"]
print("Non-Play-Pass Users:", non_play_pass["ID"].nunique())

for user_id, user_df in non_play_pass.groupby("ID"):
    total_spent = user_df["Amount Spent on In-App Purchases"].sum() + user_df["App/Game Price"].sum()
    avg_sessions = user_df["Session Count"].mean()
    print(f"User {user_id} spent ${total_spent:.2f}, sessions: {avg_sessions}")
