import argparse
import os

import gpxpy
import matplotlib.pyplot as plt
from math import radians, sin, cos, sqrt, atan2

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2)**2 + cos(phi1) * cos(phi2) * sin(dlambda / 2)**2
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
                    "time": p.time
                })
    return points


# --- Write adjusted points to GPX file ---
def write_points_to_gpx(points, output_path, track_name="Adjusted GPX track"):
    gpx = gpxpy.gpx.GPX()
    track = gpxpy.gpx.GPXTrack(name=track_name)
    segment = gpxpy.gpx.GPXTrackSegment()

    for point in points:
        segment.points.append(
            gpxpy.gpx.GPXTrackPoint(
                latitude=point["lat"],
                longitude=point["lon"],
                elevation=point["ele"],
                time=point["time"],
            )
        )

    track.segments.append(segment)
    gpx.tracks.append(track)

    with open(output_path, "w") as f:
        f.write(gpx.to_xml())

def cleaned_distance(points, max_speed_mps=None, min_move_m=0.0, verbose=False):
    """
    Conservative cleaner:
    - min_move_m removes only tiny jitter
    - max_speed_mps removes impossible jumps only if you set it
    """
    total_m = 0
    kept = [points[0]]

    removed_tiny = 0
    removed_fast = 0
    kept_segments = 0
    skipped_tiny_segments = 0
    skipped_fast_segments = 0

    prev_kept = points[0]

    for curr in points[1:]:
        d = haversine_m(
            prev_kept["lat"], prev_kept["lon"],
            curr["lat"], curr["lon"]
        )

        # Remove tiny jitter only
        if d < min_move_m:
            removed_tiny += d
            skipped_tiny_segments += 1
            continue

        # Remove impossible jumps only if requested
        if max_speed_mps is not None and prev_kept["time"] and curr["time"]:
            dt = (curr["time"] - prev_kept["time"]).total_seconds()

            if dt > 0:
                speed = d / dt
                if speed > max_speed_mps:
                    removed_fast += d
                    skipped_fast_segments += 1
                    continue

        total_m += d
        kept.append(curr)
        prev_kept = curr
        kept_segments += 1

    stats = {
        "kept_points": len(kept),
        "total_points": len(points),
        "kept_segments": kept_segments,
        "skipped_tiny_segments": skipped_tiny_segments,
        "skipped_fast_segments": skipped_fast_segments,
        "rejected_tiny_candidate_m": removed_tiny,
        "rejected_fast_candidate_m": removed_fast,
    }

    if verbose:
        print(f"Kept points: {stats['kept_points']} / {stats['total_points']}")
        print(f"Kept segments: {stats['kept_segments']}")
        print(f"Skipped tiny segments: {stats['skipped_tiny_segments']}")
        print(f"Skipped fast segments: {stats['skipped_fast_segments']}")
        print(
            "Rejected tiny candidate distance: "
            f"{stats['rejected_tiny_candidate_m'] / 1609.34:.2f} mi"
        )
        print(
            "Rejected fast candidate distance: "
            f"{stats['rejected_fast_candidate_m'] / 1609.34:.2f} mi"
        )

    return total_m, kept, stats

# ---- Command-line interface and helpers ----

def raw_distance(points):
    return sum(
        haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        for a, b in zip(points, points[1:])
    )


# --- Elevation gain calculation ---
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


def plot_diagnostic_results(results, output_path):
    thresholds = [row["min_move_m"] for row in results]
    distances = [row["distance_m"] / 1609.34 for row in results]
    gains = [row["gain_m"] * 3.28084 for row in results]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    distance_line = ax1.plot(
        thresholds,
        distances,
        marker="o",
        label="Adjusted distance (mi)",
    )
    ax1.set_xlabel("Minimum movement threshold (m)")
    ax1.set_ylabel("Adjusted distance (mi)")
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    gain_line = ax2.plot(
        thresholds,
        gains,
        marker="o",
        linestyle="--",
        label="Adjusted elevation gain (ft)",
    )
    ax2.set_ylabel("Adjusted elevation gain (ft)")

    lines = distance_line + gain_line
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc="best")

    plt.title("GPX distance and elevation gain by smoothing threshold")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


# --- Table of kept points by threshold ---
def plot_kept_points_table(results, output_path):
    rows = []

    for row in results:
        kept_points = row["kept_points"]
        total_points = row["total_points"]
        kept_fraction = kept_points / total_points if total_points else 0

        rows.append([
            f"{row['min_move_m']:g} m",
            f"{kept_points:,}",
            f"{total_points:,}",
            f"{kept_fraction * 100:.2f}%",
        ])

    fig_height = max(4, 0.35 * len(rows) + 1.5)
    fig, ax = plt.subplots(figsize=(8, fig_height))
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        colLabels=["Min move", "Kept points", "Total points", "Kept proportion"],
        loc="center",
        cellLoc="center",
        colLoc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.35)

    for (row_idx, col_idx), cell in table.get_celld().items():
        if row_idx == 0:
            cell.set_text_props(weight="bold")

    ax.set_title("Proportion of GPX points kept by smoothing threshold", pad=20)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def print_single_adjusted_distance(points, min_move_m, max_speed_mps=None, output_gpx_path=None):
    raw_m = raw_distance(points)
    raw_gain_m = elevation_gain(points)
    clean_m, kept_points, stats = cleaned_distance(
        points,
        max_speed_mps=max_speed_mps,
        min_move_m=min_move_m,
        verbose=False,
    )
    adjusted_gain_m = elevation_gain(kept_points)

    print(f"Raw distance: {raw_m / 1609.34:.2f} mi")
    print(f"Adjusted distance: {clean_m / 1609.34:.2f} mi")
    print(f"Distance difference: {(raw_m - clean_m) / 1609.34:.2f} mi")
    print()
    print(f"Raw elevation gain: {raw_gain_m * 3.28084:.0f} ft")
    print(f"Adjusted elevation gain: {adjusted_gain_m * 3.28084:.0f} ft")
    print(f"Elevation gain difference: {(raw_gain_m - adjusted_gain_m) * 3.28084:.0f} ft")
    print()
    print(f"Min move threshold: {min_move_m:g} m")
    print(f"Kept points: {stats['kept_points']} / {stats['total_points']}")

    if output_gpx_path is not None:
        write_points_to_gpx(
            kept_points,
            output_gpx_path,
            track_name=f"Adjusted GPX track, min_move={min_move_m:g}m",
        )
        print(f"Saved adjusted GPX to: {output_gpx_path}")


def print_diagnostic_table(points, thresholds, max_speed_mps=None, plot_path=None, table_path=None):
    raw_m = raw_distance(points)
    raw_gain_m = elevation_gain(points)

    print(f"Raw distance: {raw_m / 1609.34:.2f} mi")
    print(f"Raw elevation gain: {raw_gain_m * 3.28084:.0f} ft")
    print()
    results = []

    for min_move in thresholds:
        clean_m, kept_points, stats = cleaned_distance(
            points,
            max_speed_mps=max_speed_mps,
            min_move_m=min_move,
            verbose=True,
        )
        adjusted_gain_m = elevation_gain(kept_points)
        results.append({
            "min_move_m": min_move,
            "distance_m": clean_m,
            "gain_m": adjusted_gain_m,
            "kept_points": len(kept_points),
            "total_points": len(points),
        })
        print(
            f"min_move={min_move:>5g} m | "
            f"distance={clean_m / 1609.34:>6.2f} mi | "
            f"gain={adjusted_gain_m * 3.28084:>7.0f} ft | "
            f"distance_diff={(raw_m - clean_m) / 1609.34:>6.2f} mi | "
            f"gain_diff={(raw_gain_m - adjusted_gain_m) * 3.28084:>7.0f} ft | "
            f"kept={len(kept_points):>6} / {len(points)}"
        )
        print()

    if plot_path is not None:
        plot_diagnostic_results(results, plot_path)
        print(f"Saved diagnostic plot to: {plot_path}")

    if table_path is not None:
        plot_kept_points_table(results, table_path)
        print(f"Saved kept-points table to: {table_path}")


def parse_thresholds(threshold_string):
    return [float(value.strip()) for value in threshold_string.split(",") if value.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Estimate GPX distance after removing small GPS jitter movements."
    )
    parser.add_argument("gpx_file", help="Path to the GPX file to analyze.")
    parser.add_argument(
        "--min-move",
        type=float,
        default=10.0,
        help="Minimum movement in meters required to keep a new point. Default: 10.0",
    )
    parser.add_argument(
        "--max-speed",
        type=float,
        default=None,
        help="Optional maximum speed in m/s. Segments faster than this are rejected.",
    )
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Print a full diagnostic table across several min-move thresholds.",
    )
    parser.add_argument(
        "--thresholds",
        default=None,
        help="Comma-separated min-move thresholds for --diagnostic. Default: 0,2,4,...,30",
    )
    parser.add_argument(
        "--plot-path",
        default=None,
        help="Optional output path for the diagnostic plot. Default: <gpx filename>_diagnostic.png",
    )
    parser.add_argument(
        "--table-path",
        default=None,
        help="Optional output path for the diagnostic kept-points PNG table. Default: <gpx filename>_kept_points_table.png",
    )
    parser.add_argument(
        "--output-gpx",
        default=None,
        help="Optional output path for the adjusted GPX file. Default in single mode: <gpx filename>_adjusted_<min_move>m.gpx",
    )

    args = parser.parse_args()
    points = load_points(args.gpx_file)

    if not points:
        raise ValueError(f"No track points found in {args.gpx_file}")

    if args.diagnostic:
        if args.thresholds is None:
            thresholds = list(range(0, 31, 2))
        else:
            thresholds = parse_thresholds(args.thresholds)

        if args.plot_path is None:
            base_name = os.path.splitext(os.path.basename(args.gpx_file))[0]
            plot_path = f"{base_name}_diagnostic.png"
        else:
            plot_path = args.plot_path

        if args.table_path is None:
            base_name = os.path.splitext(os.path.basename(args.gpx_file))[0]
            table_path = f"{base_name}_kept_points_table.png"
        else:
            table_path = args.table_path

        print_diagnostic_table(
            points,
            thresholds,
            max_speed_mps=args.max_speed,
            plot_path=plot_path,
            table_path=table_path,
        )
    else:
        if args.output_gpx is None:
            base_name = os.path.splitext(os.path.basename(args.gpx_file))[0]
            min_move_label = f"{args.min_move:g}".replace(".", "p")
            output_gpx_path = f"{base_name}_adjusted_{min_move_label}m.gpx"
        else:
            output_gpx_path = args.output_gpx

        print_single_adjusted_distance(
            points,
            min_move_m=args.min_move,
            max_speed_mps=args.max_speed,
            output_gpx_path=output_gpx_path,
        )


if __name__ == "__main__":
    main()