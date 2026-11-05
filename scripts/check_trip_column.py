import pandas as pd

df = pd.read_csv(
    r"C:\Users\annam\Downloads\export.csv",
    nrows=0
)

for column in df.columns:
    if "trip" in column.lower():
        print(repr(column))