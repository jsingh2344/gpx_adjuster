import argparse
import gpxpy
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


def print_single_adjusted_distance(points, min_move_m, max_speed_mps=None):
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


def print_diagnostic_table(points, thresholds, max_speed_mps=None):
    raw_m = raw_distance(points)
    raw_gain_m = elevation_gain(points)

    print(f"Raw distance: {raw_m / 1609.34:.2f} mi")
    print(f"Raw elevation gain: {raw_gain_m * 3.28084:.0f} ft")
    print()

    for min_move in thresholds:
        clean_m, kept_points, stats = cleaned_distance(
            points,
            max_speed_mps=max_speed_mps,
            min_move_m=min_move,
            verbose=True,
        )
        adjusted_gain_m = elevation_gain(kept_points)
        print(
            f"min_move={min_move:>5g} m | "
            f"distance={clean_m / 1609.34:>6.2f} mi | "
            f"gain={adjusted_gain_m * 3.28084:>7.0f} ft | "
            f"distance_diff={(raw_m - clean_m) / 1609.34:>6.2f} mi | "
            f"gain_diff={(raw_gain_m - adjusted_gain_m) * 3.28084:>7.0f} ft | "
            f"kept={len(kept_points):>6} / {len(points)}"
        )
        print()


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
        default="0,1,2,3,5,8,10,15,20",
        help="Comma-separated min-move thresholds for --diagnostic. Default: 0,1,2,3,5,8,10,15,20",
    )

    args = parser.parse_args()
    points = load_points(args.gpx_file)

    if not points:
        raise ValueError(f"No track points found in {args.gpx_file}")

    if args.diagnostic:
        thresholds = parse_thresholds(args.thresholds)
        print_diagnostic_table(points, thresholds, max_speed_mps=args.max_speed)
    else:
        print_single_adjusted_distance(
            points,
            min_move_m=args.min_move,
            max_speed_mps=args.max_speed,
        )


if __name__ == "__main__":
    main()