import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import plotly.graph_objects as go
import shutil
import kagglehub
import os
os.makedirs("images", exist_ok=True)

def load_ufc_data(folder="data", filename="ufc-master.csv", refresh=False):
    """Download the UFC dataset (if needed) and return it as a DataFrame with a short summary."""
    file_path = os.path.join(folder, filename)

    # Download only if the file isn't already there (or if refresh=True)
    if refresh or not os.path.exists(file_path):
        try:
            kagglehub.dataset_download("mdabbert/ultimate-ufc-dataset",
                                       output_dir=folder, force_download=refresh)
        except TypeError:   # older kagglehub without output_dir
            cache = kagglehub.dataset_download("mdabbert/ultimate-ufc-dataset")
            os.makedirs(folder, exist_ok=True)
            for f in os.listdir(cache):
                shutil.copy(os.path.join(cache, f), folder)

    df = pd.read_csv(file_path)
    df["date"] = pd.to_datetime(df["date"])

    size_mb = os.path.getsize(file_path) / 1e6
    print(f"Loaded {filename} ({size_mb:.1f} MB) from '{folder}'")
    print(f"{df.shape[0]:,} fights, {df.shape[1]} columns")
    print(f"Dates: {df['date'].min():%Y-%m-%d} to {df['date'].max():%Y-%m-%d}")
    print(f"Missing finish type: {df['finish'].isna().sum()} fights")
    return df

def plot_share_bar(series, title, top_n=4, colors=None, labels=None, save_as=None):
    """Single stacked bar showing the % share of the top_n values, with the rest grouped as 'Other'."""
    top = series.value_counts().head(top_n).index
    grouped = series.where(series.isin(top), "Other")   # NaN becomes "Other" too
    counts = grouped.value_counts()
    counts = counts[list(top) + ["Other"]]               # keep "Other" last
    pct = counts / counts.sum() * 100

    if colors is None:
        colors = ["steelblue", "indianred", "seagreen", "goldenrod", "mediumpurple", "teal"][:top_n] + ["lightgray"]

    fig, ax = plt.subplots(figsize=(10, 2.5))
    left = 0
    for (label, value), color in zip(pct.items(), colors):
        name = labels.get(label, label) if labels else label
        ax.barh("All fights", value, left=left, color=color, label=f"{name} ({value:.0f}%)")
        left += value

    ax.set_xlabel("% of fights")
    ax.set_title(title)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.4), ncol=top_n + 1, frameon=False)
    plt.tight_layout()
    if save_as:
        plt.savefig(save_as, dpi=150, bbox_inches="tight")
    plt.show()
    
    
def plot_counts(series, title, xlabel="Number of fights", top_n=10, color="steelblue"):
    """Draw a horizontal bar chart from a pandas Series of values."""
    counts = series.value_counts().head(top_n)

    plt.figure(figsize=(8, 5))
    sns.barplot(x=counts.values, y=counts.index, color=color)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("")
    plt.tight_layout()
    plt.show()

def plot_rate_by_group(df, group_col, finish_value, title, min_fights=50, color="steelblue", save_as=None):
    """Bar chart of the % of fights ending in a given finish, per group (e.g. weight class)."""
    total = df[group_col].value_counts()
    hits = df[df["finish"] == finish_value][group_col].value_counts()

    rate = (hits / total * 100)[total >= min_fights].dropna().sort_values(ascending=False)

    plt.figure(figsize=(8, 5))
    sns.barplot(x=rate.values, y=rate.index, color=color)
    plt.title(title)
    plt.xlabel(f"% of fights ending in {finish_value}")
    plt.ylabel("")
    plt.tight_layout()
    if save_as:
        plt.savefig(save_as, dpi=150, bbox_inches="tight")

    overall = (df["finish"] == finish_value).mean() * 100
    plt.axvline(overall, color="gray", linestyle="--", label=f"Overall average ({overall:.0f}%)")
    plt.legend(loc="lower right", frameon=False)
    
    plt.show()

def plot_finishes_by_group(df, group_col="weight_class", finish_col="finish", top_n=4,
                           min_fights=50, exclude=None, labels=None,
                           weight_order=None, title="How fights end, by weight class",
                           save_html=None):
    """Interactive stacked bars of finish types per group, built directly from the raw data."""
    # 1. Clean the rows
    if exclude:
        df = df[~df[group_col].isin(exclude)]

    # 2. Keep the top finish types, group the rest (and NaN) as "Other"
    top = df[finish_col].value_counts().head(top_n).index
    grouped = df[finish_col].where(df[finish_col].isin(top), "Other")
    order = list(top) + ["Other"]

    # 3. Count fights per group and finish, then convert to percentages
    counts = df.assign(_finish=grouped).groupby([group_col, "_finish"]).size().unstack(fill_value=0)[order]
    counts = counts[counts.sum(axis=1) >= min_fights]
    pct = counts.div(counts.sum(axis=1), axis=0) * 100
    if labels:
        pct = pct.rename(columns=labels)

    # 4. Draw the chart
    cols = list(pct.columns)
    colors = ["steelblue", "indianred", "seagreen", "goldenrod", "mediumpurple", "teal"][:len(cols) - 1] + ["lightgray"]

    fig = go.Figure()
    for col, color in zip(cols, colors):
        fig.add_bar(
            y=pct.index, x=pct[col], name=col, orientation="h", marker_color=color,
            hovertemplate="%{y}<br>" + col + ": %{x:.1f}%<extra></extra>",
        )

    def by_value(col):
        return pct[col].sort_values().index.tolist()   # ascending puts the largest bar on top

    buttons = [
        dict(label=f"Sort by {col}", method="relayout",
             args=[{"yaxis.categoryorder": "array", "yaxis.categoryarray": by_value(col)}])
        for col in cols
    ]

    start = by_value(cols[0])
    if weight_order:
        by_weight = [w for w in weight_order if w in pct.index][::-1]   # lightest at the top
        buttons.insert(0, dict(label="Sort by weight", method="relayout",
                               args=[{"yaxis.categoryorder": "array", "yaxis.categoryarray": by_weight}]))
        start = by_weight

    fig.update_layout(
        barmode="stack",
        title=title,
        xaxis_title="% of fights",
        yaxis=dict(categoryorder="array", categoryarray=start),
        updatemenus=[dict(buttons=buttons, direction="down", x=0, y=1.15, xanchor="left")],
        legend=dict(orientation="h", y=-0.15),
        height=550,
    )
    if save_html:
        fig.write_html(save_html)
    fig.show()

def plot_avg_by_group(df, value_cols, title, xlabel, group_col="weight_class",
                      exclude=None, min_rows=50, color="seagreen", save_as=None):
    """Bar chart of the mean of value_cols (e.g. red and blue corner) per group, sorted high to low."""
    if exclude:
        df = df[~df[group_col].isin(exclude)]

    df = df.assign(_value=df[value_cols].mean(axis=1))   # average of both fighters per fight

    stats = df.groupby(group_col)["_value"].agg(["mean", "size"])
    stats = stats[stats["size"] >= min_rows].sort_values("mean", ascending=False)

    plt.figure(figsize=(8, 5))
    sns.barplot(x=stats["mean"], y=stats.index, color=color, order=stats.index)

    overall = df["_value"].mean()
    plt.axvline(overall, color="gray", linestyle="--", label=f"Overall average ({overall:.2f})")
    plt.legend(loc="lower right", frameon=False)

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("")
    plt.tight_layout()
    if save_as:
        plt.savefig(save_as, dpi=150, bbox_inches="tight")
    plt.show()

def plot_rate_over_time(df, finish_value, title, color="steelblue", min_fights=20,
                        show_count=True, save_as=None):
    """Line chart of the % of fights ending in finish_value, per year."""
    df = df.assign(year=pd.to_datetime(df["date"]).dt.year)

    yearly = df.groupby("year").agg(
        fights=("finish", "size"),
        hits=("finish", lambda s: (s == finish_value).sum()),
    )
    yearly = yearly[yearly["fights"] >= min_fights]
    yearly["rate"] = yearly["hits"] / yearly["fights"] * 100

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(yearly.index, yearly["rate"], color=color, marker="o")

    overall = (df["finish"] == finish_value).mean() * 100
    ax.axhline(overall, color="gray", linestyle="--", label=f"Overall average ({overall:.0f}%)")

    if show_count:   # faint bars on a second axis show how many fights each year has
        ax2 = ax.twinx()
        ax2.bar(yearly.index, yearly["fights"], color="lightgray", alpha=0.4, zorder=0)
        ax2.set_ylabel("Fights per year")
        ax.set_zorder(ax2.get_zorder() + 1)
        ax.patch.set_visible(False)

    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel(f"% of fights ending in {finish_value}")
    ax.legend(loc="upper right", frameon=False)
    plt.tight_layout()
    if save_as:
        plt.savefig(save_as, dpi=150, bbox_inches="tight")
    plt.show()