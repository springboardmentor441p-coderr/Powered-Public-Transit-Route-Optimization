import pandas as pd

file_path = r"C:\Users\annam\Downloads\export.csv"

speed_data = {}

print("Analyzing hourly bus speeds by borough...")

for chunk in pd.read_csv(
    file_path,
    usecols=["Borough", "Timestamp", "Average Road Speed"],
    dtype="string",
    chunksize=100000
):
    timestamps = pd.to_datetime(
        chunk["Timestamp"],
        format="mixed",
        errors="coerce"
    )

    chunk["Hour"] = timestamps.dt.hour

    chunk["Average Road Speed"] = pd.to_numeric(
        chunk["Average Road Speed"],
        errors="coerce"
    )

    grouped = chunk.groupby(
        ["Borough", "Hour"]
    )["Average Road Speed"].agg(["sum", "count"])

    for (borough, hour), row in grouped.iterrows():
        key = (borough, hour)

        if key not in speed_data:
            speed_data[key] = [0, 0]

        speed_data[key][0] += row["sum"]
        speed_data[key][1] += row["count"]

results = []

for (borough, hour), values in speed_data.items():
    if values[1] > 0:
        results.append({
            "Borough": borough,
            "Hour": hour,
            "Average Speed": values[0] / values[1],
            "Records": values[1]
        })

result_df = pd.DataFrame(results)

print("\nSLOWEST 3 HOURS IN EACH BOROUGH:")

for borough in sorted(result_df["Borough"].unique()):
    print("\n", borough)

    borough_data = result_df[
        result_df["Borough"] == borough
    ]

    print(
        borough_data.sort_values("Average Speed")
        .head(3)
        .to_string(index=False)
    )