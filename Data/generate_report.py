from ydata_profiling import ProfileReport  
import pandas as pd

def generate_report(df, filename="Data/play_data_report.html"):
    profile = ProfileReport(df, title="Play Store Data Report", explorative=True)
    profile.to_file(filename)
    print(f"✅ Report generated: {filename}")

df = pd.read_excel("Data/play_data.xlsx")
print("Total Rows:", df.shape[0])
generate_report(df, "Data/play_data_report.html")

# Generate report with optimized settings   
profile = ProfileReport(df, title="Play Store Data Report", explorative=True, minimal=True)
profile.to_file("Data/play_data_report_optimized.html")
print("✅ Optimized report generated: play_data_report_optimized.html")