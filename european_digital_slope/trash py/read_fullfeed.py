import pandas as pd
from datetime import datetime

# Set pandas display options to show all rows without truncation
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.float_format", lambda x: "%.3f" % x)
pd.options.display.min_rows = 1000  # Ensure no truncation with "..."


def main():
    # Convert target timestamps to Unix timestamps
    start_time = datetime(2025, 5, 21, 9, 47, 56).timestamp()
    end_time = datetime(2025, 5, 21, 9, 48, 3).timestamp()

    # Read the CSV file
    df = pd.read_csv(
        "21-May-25-fullfeed.csv",
        names=[
            "timestamp",
            "bid",
            "ask",
            "empty",
            "mid",
            "source",
            "empty2",
            "metadata",
        ],
    )

    # Filter data between timestamps
    mask = (df["timestamp"] >= start_time) & (df["timestamp"] <= end_time)
    filtered_df = df[mask].copy()

    # Convert timestamp to datetime
    filtered_df["datetime"] = pd.to_datetime(filtered_df["timestamp"], unit="s")

    # Display filtered data
    print("\nData between timestamps:")
    print(filtered_df[["datetime", "bid", "ask", "mid"]].to_string())

    # Calculate statistics for entire dataset
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    df["second"] = df["datetime"].dt.floor("s")
    all_ticks = df.groupby("second").size()

    print("\nEntire Dataset Statistics:")
    print("========================")
    print(f"Total number of ticks: {len(df)}")
    print(f"Total number of seconds: {len(all_ticks)}")
    print(f"Average ticks per second: {all_ticks.mean():.2f}")
    print(f"Minimum ticks per second: {all_ticks.min()}")
    print(f"Maximum ticks per second: {all_ticks.max()}")
    print(f"Standard deviation: {all_ticks.std():.2f}")

    # Calculate distribution and unique values per second
    ticks_distribution = all_ticks.value_counts().sort_index()
    percentages = (ticks_distribution / len(all_ticks) * 100).round(2)

    # Calculate average unique values for each tick count
    unique_values = {}
    for ticks in ticks_distribution.index:
        # Get seconds with this tick count
        seconds_with_ticks = all_ticks[all_ticks == ticks].index
        # For each such second, count unique mid prices
        unique_counts = []
        for second in seconds_with_ticks:
            second_data = df[df["second"] == second]
            unique_count = second_data["mid"].nunique()
            unique_counts.append(unique_count)
        # Calculate average unique values for this tick count
        unique_values[ticks] = sum(unique_counts) / len(unique_counts)

    print("\nDistribution of Ticks per Second:")
    print("===============================")
    print("Ticks  Count     Percentage  Cumulative  Avg Unique Values")
    print("-------------------------------------------------------")
    cumulative = 0
    for ticks, percentage in percentages.items():
        count = ticks_distribution[ticks]
        cumulative += percentage
        avg_unique = unique_values[ticks]
        print(
            f"{ticks:5d}  {count:8d}  {percentage:8.2f}%  {cumulative:8.2f}%  {avg_unique:8.2f}"
        )


if __name__ == "__main__":
    main()
