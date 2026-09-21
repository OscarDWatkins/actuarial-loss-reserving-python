import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------------------------
# 1. Choosing Data to Analyse
# ---------------------------------------------------------

# Read the CSV file into a DataFrame
df = pd.read_csv("auto_dataset.csv")

# Filter companies with complete 10-year development histories
filtered_df = df.groupby("GRNAME").filter(lambda x: len(x) == 100)
filtered_df.to_csv("filtered_data.csv", index=False)

# Select target company data
company_df = df[df["GRNAME"] == "Employers Mut Co Of Des Moines"].copy()


# ---------------------------------------------------------
# 2. Creating Loss Development Triangles
# ---------------------------------------------------------

# Subset required columns for cumulative paid claims
cum_df = company_df[["AccidentYear", "DevelopmentLag", "CumPaidLoss"]]

# Pivot into a cumulative paid claims triangle
cum_triangle = cum_df.pivot(
    index="AccidentYear", columns="DevelopmentLag", values="CumPaidLoss"
)

# Optional: Incremental paid claims triangle
inc_triangle = cum_triangle.diff(axis=1)
inc_triangle[1] = cum_triangle[1]

# Artificially apply cutoff year to simulate unobserved development
cutoff_year = 2007

lags_cum = cum_triangle.columns.astype(int)
years_cum = cum_triangle.index.astype(int)

# Create matrix of Evaluation Years (AccidentYear + DevelopmentLag - 1)
eval_years = np.array(years_cum)[:, None] + np.array(lags_cum)[None, :] - 1
cum_triangle_final = cum_triangle.where(eval_years <= cutoff_year)
cum_triangle_final.to_csv("cum_triangle.csv")


# ---------------------------------------------------------
# 3. Calculating Link Ratios & Cumulative Link Ratios
# ---------------------------------------------------------

link_ratios = []
cols = cum_triangle_final.columns

for j in range(len(cols) - 1):
    current_col = cols[j]
    next_col = cols[j + 1]

    # Filter out unobserved (NaN) cells
    valid_data = cum_triangle_final[[current_col, next_col]].dropna()

    sum_curr = valid_data[current_col].sum()
    sum_next = valid_data[next_col].sum()

    # Volume-weighted link ratio: sum(column c+1) / sum(column c)
    current_link_ratio = sum_next / sum_curr
    link_ratios.append(current_link_ratio)

# Calculate Cumulative Link Ratios (Factors to Ultimate)
cum_link_ratios = np.cumprod(link_ratios[::-1])[::-1]
cum_link_ratios = np.append(cum_link_ratios, 1.0)


# ---------------------------------------------------------
# 4. Projecting Ultimate Claims and Reserves
# ---------------------------------------------------------

ultimates = []
latest_paid_claims = []
applied_cum_ratios = []

n = len(cum_triangle_final)

# Project ultimate claims for each accident year
for i in range(n):
    diag_col_idx = n - 1 - i
    latest_val = cum_triangle_final.iloc[i, diag_col_idx]
    matching_cum_ratio = cum_link_ratios[diag_col_idx]

    row_ultimate = latest_val * matching_cum_ratio

    ultimates.append(row_ultimate)
    latest_paid_claims.append(latest_val)
    applied_cum_ratios.append(matching_cum_ratio)

# Fill bottom-right unobserved triangle cells
for i in range(n):
    diag_col_idx = n - 1 - i
    for j in range(n):
        if j > diag_col_idx:
            cum_triangle_final.iloc[i, j] = ultimates[i] / cum_link_ratios[j]

cum_triangle_final.to_csv("completed_cum_triangle.csv")

# Total Reserve required = Ultimate Claims - Latest Paid Claims
total_reserves = [ultimates[i] - latest_paid_claims[i] for i in range(n)]


# ---------------------------------------------------------
# 5. Formatting the Final Reserve Summary Table
# ---------------------------------------------------------

accident_years = cum_triangle_final.index

reserve_summary = pd.DataFrame(
    {
        "Accident_Year": accident_years,
        "Latest_Paid": latest_paid_claims,
        "Cumulative_Link_Ratio": applied_cum_ratios,
        "Ultimate_Claims": ultimates,
        "Total_Reserve": total_reserves,
    }
)

# Add portfolio total row
total_row = pd.DataFrame(
    {
        "Accident_Year": ["Total"],
        "Latest_Paid": [sum(latest_paid_claims)],
        "Cumulative_Link_Ratio": [np.nan],
        "Ultimate_Claims": [sum(ultimates)],
        "Total_Reserve": [sum(total_reserves)],
    }
)

reserve_summary = pd.concat([reserve_summary, total_row], ignore_index=True)

print("\n--- Final Actuarial Reserve Summary ---")
print(reserve_summary.to_string(index=False))
reserve_summary.to_csv("Reserve_Summary.csv", index=False)


# ---------------------------------------------------------
# 6. Visualisations
# ---------------------------------------------------------

# Chart 1: Loss Development Curves
plt.figure(figsize=(10, 6))
for i in range(n):
    plt.plot(
        cum_triangle_final.columns,
        cum_triangle_final.iloc[i, :],
        marker="o",
        label=f"AY {accident_years[i]}",
    )

plt.title("Claims Development Curves (Projected to Ultimate)")
plt.xlabel("Development Lag")
plt.ylabel("Cumulative Paid Claims ($)")
plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
plt.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()
plt.savefig("development_curves.png", dpi=300)

# Chart 2: Stacked Bar Chart for Paid vs Required Reserve
plt.figure(figsize=(9, 5))
x_labels = accident_years.astype(str)

plt.bar(x_labels, latest_paid_claims, label="Latest Paid Claims", color="#1f77b4")
plt.bar(
    x_labels,
    total_reserves,
    bottom=latest_paid_claims,
    label="Required Reserve",
    color="#ff7f0e",
)

plt.title("Paid Claims vs. Required Outstanding Reserve by Accident Year")
plt.xlabel("Accident Year")
plt.ylabel("Amount ($)")
plt.legend()
plt.grid(axis="y", linestyle="--", alpha=0.6)
plt.tight_layout()
plt.savefig("reserve_breakdown.png", dpi=300)

plt.show()
