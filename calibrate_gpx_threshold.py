import argparse
import os
from math import radians, sin, cos, sqrt, atan2

import gpxpy
import pandas as pd
import matplotlib.pyplot as plt


M_PER_MI = 1609.34
FT_PER_M = 3.28084


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def load_points(gpx_file):
    with open(gpx_file, "r") as f:
        gpx = gpxpy.parse(f)

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                points.append({
                    "lat": p.latitude,
                    "lon": p.longitude,
                    "ele": p.elevation,
                    "time": p.time,
                })

    return points


def raw_distance(points):
    return sum(
        haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        for a, b in zip(points, points[1:])
    )


def elevation_gain(points):
    gain_m = 0
    prev_ele = None

    for point in points:
        ele = point["ele"]
        if ele is None:
            continue

        if prev_ele is not None and ele > prev_ele:
            gain_m += ele - prev_ele

        prev_ele = ele

    return gain_m


def clean_points(points, min_move_m):
    """
    Keep a new point only once it is at least min_move_m away from the last kept point.
    This matches the cleaning logic from gpx_adjuster.py.
    """
    if not points:
        return []

    kept = [points[0]]
    prev_kept = points[0]

    for curr in points[1:]:
        d = haversine_m(
            prev_kept["lat"], prev_kept["lon"],
            curr["lat"], curr["lon"],
        )

        if d < min_move_m:
            continue

        kept.append(curr)
        prev_kept = curr

    return kept


def analyze_track(gpx_path, true_distance_mi, true_gain_ft, thresholds):
    points = load_points(gpx_path)

    rows = []

    for threshold in thresholds: #ex. 10, 20, 30m
        kept = clean_points(points, threshold)

        adjusted_distance_mi = raw_distance(kept) / M_PER_MI
        adjusted_gain_ft = elevation_gain(kept) * FT_PER_M

        distance_error_mi = adjusted_distance_mi - true_distance_mi
        gain_error_ft = adjusted_gain_ft - true_gain_ft

        distance_abs_pct_error = abs(distance_error_mi) / true_distance_mi * 100
        gain_abs_pct_error = abs(gain_error_ft) / true_gain_ft * 100
        distance_pct_error = distance_error_mi / true_distance_mi * 100
        gain_pct_error = gain_error_ft / true_gain_ft * 100

        rows.append({
            "file": os.path.basename(gpx_path),
            "threshold_m": threshold,
            "kept_points": len(kept),
            "total_points": len(points),
            "kept_pct": len(kept) / len(points) * 100 if points else 0,

            "true_distance_mi": true_distance_mi,
            "adjusted_distance_mi": adjusted_distance_mi,
            "distance_error_mi": distance_error_mi,
            "distance_abs_error_mi": abs(distance_error_mi),
            "distance_abs_pct_error": distance_abs_pct_error,
            "distance_pct_error": distance_pct_error,

            "true_gain_ft": true_gain_ft,
            "adjusted_gain_ft": adjusted_gain_ft,
            "gain_error_ft": gain_error_ft,
            "gain_abs_error_ft": abs(gain_error_ft),
            "gain_abs_pct_error": gain_abs_pct_error,
            "gain_pct_error": gain_pct_error,
        })

    return rows


def summarize_thresholds(results_df):
    """
    Calibrate solely on distance error.

    Elevation error is still summarized and plotted, but it does not affect
    threshold selection.
    """
    grouped = results_df.groupby("threshold_m").agg(
        mean_distance_pct_error=("distance_pct_error", "mean"),
        mean_gain_pct_error=("gain_pct_error", "mean"),
        mean_distance_abs_pct_error=("distance_abs_pct_error", "mean"),
        mean_gain_abs_pct_error=("gain_abs_pct_error", "mean"),
        mean_distance_error_mi=("distance_error_mi", "mean"),
        mean_gain_error_ft=("gain_error_ft", "mean"),
        mean_distance_abs_error_mi=("distance_abs_error_mi", "mean"),
        mean_gain_abs_error_ft=("gain_abs_error_ft", "mean"),
        mean_kept_pct=("kept_pct", "mean"),
    ).reset_index()

    grouped["distance_score"] = grouped["mean_distance_abs_pct_error"]

    return grouped.sort_values("distance_score")


def plot_threshold_summary(summary_df, output_path):
    # Sort by threshold so lines connect left-to-right.
    summary_df = summary_df.sort_values("threshold_m")

    # Best point is the threshold with the lowest mean absolute distance error.
    best_row = summary_df.loc[summary_df["mean_distance_abs_pct_error"].idxmin()]
    best_threshold = best_row["threshold_m"]
    best_distance_error = best_row["mean_distance_abs_pct_error"]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Mean absolute distance error: solid line.
    ax1.plot(
        summary_df["threshold_m"],
        summary_df["mean_distance_abs_pct_error"],
        marker="o",
        label="Distance mean absolute error (%)",
    )

    # Mean absolute elevation gain error: solid line.
    ax1.plot(
        summary_df["threshold_m"],
        summary_df["mean_gain_abs_pct_error"],
        marker="o",
        label="Elevation gain mean absolute error (%)",
    )

    # Mean directional distance error: dashed line.
    ax1.plot(
        summary_df["threshold_m"],
        summary_df["mean_distance_pct_error"],
        marker="o",
        linestyle="--",
        label="Distance mean directional error (%)",
    )

    # Highlight the minimum distance-error point in red.
    ax1.scatter(
        [best_threshold],
        [best_distance_error],
        color="red",
        s=90,
        zorder=5,
        label=f"Lowest distance error: {best_threshold:g} m",
    )

    # Horizontal red line at the minimum error level.
    ax1.axhline(
        best_distance_error,
        color="red",
        linestyle=":",
        linewidth=1.5,
        label=f"Minimum distance error: {best_distance_error:.2f}%",
    )

    # Zero line helps interpret directional error.
    ax1.axhline(
        0,
        color="black",
        linestyle="--",
        linewidth=1,
        alpha=0.5,
    )

    ax1.set_xlabel("Minimum movement threshold (m)")
    ax1.set_ylabel("Mean percent error")
    ax1.set_title("GPX threshold calibration")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def plot_track_errors(results_df, best_threshold, output_path):
    subset = results_df[results_df["threshold_m"] == best_threshold].copy()

    labels = subset["file"].tolist()
    x = range(len(labels))

    fig, ax1 = plt.subplots(figsize=(11, 6))

    ax1.bar(
        [i - 0.2 for i in x],
        subset["distance_pct_error"],
        width=0.4,
        label="Distance directional error (%)",
    )
    ax1.bar(
        [i + 0.2 for i in x],
        subset["gain_pct_error"],
        width=0.4,
        label="Elevation gain directional error (%)",
    )

    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, rotation=45, ha="right")
    ax1.set_ylabel("Directional percent error")
    ax1.set_title(f"Per-track error at {best_threshold:g} m threshold")
    ax1.legend()
    ax1.axhline(0, linestyle="--", linewidth=1)
    ax1.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def parse_thresholds(start, stop, step):
    # Includes stop if it lands exactly on the sequence.
    thresholds = []
    x = start
    while x <= stop + 1e-9:
        thresholds.append(round(x, 6))
        x += step
    return thresholds


def main():
    parser = argparse.ArgumentParser(
        description="Calibrate GPX min-move threshold against tracks with known truth distance/elevation."
    )
    parser.add_argument(
        "truth_csv",
        help="CSV with columns: file,true_distance_mi,true_gain_ft",
    )
    parser.add_argument(
        "--gpx-dir",
        default=".",
        help="Directory containing GPX files. Default: current directory.",
    )
    parser.add_argument(
        "--start",
        type=float,
        default=0,
        help="Minimum threshold to test, in meters. Default: 0",
    )
    parser.add_argument(
        "--stop",
        type=float,
        default=30,
        help="Maximum threshold to test, in meters. Default: 30",
    )
    parser.add_argument(
        "--step",
        type=float,
        default=1,
        help="Threshold step size, in meters. Default: 1",
    )
    parser.add_argument(
        "--out-prefix",
        default="threshold_calibration",
        help="Prefix for output CSVs and plots.",
    )

    args = parser.parse_args()

    truth = pd.read_csv(args.truth_csv)
    truth = truth.rename(columns={
        "File": "file",
        "Mi": "true_distance_mi",
        "Elev": "true_gain_ft",
    })

    required = {"file", "true_distance_mi", "true_gain_ft"}
    missing = required - set(truth.columns)
    if missing:
        raise ValueError(f"Missing required columns in truth CSV: {missing}")

    thresholds = parse_thresholds(args.start, args.stop, args.step)

    all_rows = []

    for _, row in truth.iterrows():
        gpx_path = os.path.join(args.gpx_dir, row["file"])

        if not os.path.exists(gpx_path):
            raise FileNotFoundError(f"Could not find GPX file: {gpx_path}")

        print(f"Analyzing {gpx_path}...")

        all_rows.extend(
            analyze_track(
                gpx_path=gpx_path,
                true_distance_mi=float(row["true_distance_mi"]),
                true_gain_ft=float(row["true_gain_ft"]),
                thresholds=thresholds,
            )
        )

    results_df = pd.DataFrame(all_rows)
    summary_df = summarize_thresholds(results_df)

    best = summary_df.iloc[0]
    best_threshold = best["threshold_m"]

    results_path = f"{args.out_prefix}_per_track_results.csv"
    summary_path = f"{args.out_prefix}_summary.csv"
    summary_plot_path = f"{args.out_prefix}_summary.png"
    track_error_plot_path = f"{args.out_prefix}_best_threshold_track_errors.png"

    results_df.to_csv(results_path, index=False)
    summary_df.to_csv(summary_path, index=False)

    plot_threshold_summary(summary_df, summary_plot_path)
    plot_track_errors(results_df, best_threshold, track_error_plot_path)

    print()
    print("Best threshold:")
    print(f"  {best_threshold:g} m")
    print()
    print("Mean errors at best threshold:")
    print(f"  Distance absolute error: {best['mean_distance_abs_pct_error']:.2f}%")
    print(f"  Distance directional error: {best['mean_distance_pct_error']:.2f}%")
    print(f"  Elevation gain absolute error: {best['mean_gain_abs_pct_error']:.2f}%")
    print(f"  Elevation gain directional error: {best['mean_gain_pct_error']:.2f}%")
    print(f"  Distance-only score: {best['distance_score']:.2f}%")
    print(f"  Mean kept points: {best['mean_kept_pct']:.2f}%")
    print()
    print("Saved:")
    print(f"  {results_path}")
    print(f"  {summary_path}")
    print(f"  {summary_plot_path}")
    print(f"  {track_error_plot_path}")


if __name__ == "__main__":
    main()