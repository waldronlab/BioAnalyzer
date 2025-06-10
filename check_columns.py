import pandas as pd
from collections import Counter

# First, read the raw file to get the header line
with open('data/full_dump.csv', 'r') as f:
    # Skip the first two comment lines
    f.readline()  # Skip first line
    f.readline()  # Skip second line
    header_line = f.readline().strip()  # Get the header line

# Split the header line into column names
column_names = header_line.split(',')

# Find duplicate columns
column_counts = Counter(column_names)
duplicates = {col: count for col, count in column_counts.items() if count > 1}

print("\nOriginal column names:")
for i, col in enumerate(column_names, 1):
    print(f"{i}. {col}")

if duplicates:
    print("\nDuplicate columns found:")
    for col, count in duplicates.items():
        print(f"'{col}' appears {count} times")

    # Make column names unique by adding a suffix
    unique_names = []
    seen_counts = {}
    
    for col in column_names:
        if column_counts[col] > 1:
            seen_counts[col] = seen_counts.get(col, 0) + 1
            unique_names.append(f"{col}_{seen_counts[col]}")
        else:
            unique_names.append(col)
    
    print("\nUnique column names (after adding suffixes):")
    for i, col in enumerate(unique_names, 1):
        print(f"{i}. {col}")
    
    # Now read the CSV with unique column names
    df = pd.read_csv('data/full_dump.csv', skiprows=2, names=unique_names)
else:
    # If no duplicates, use original names
    df = pd.read_csv('data/full_dump.csv', skiprows=2, names=column_names)

print("\nFirst row of data:")
print(df.iloc[0]) 