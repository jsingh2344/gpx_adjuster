# GPX Adjuster

To this point, I've recorded all of my Strava activities using my iPhone. In Washington, D.C., the distance and elevation figures seem mostly accurate, but in Wyoming, 
they can be obviously, and wildly, inaccurate. For example: in August 2025, I climbed a version of the Cathedral Traverse in the Tetons. 
A realistic mileage/elevation split would maybe be 15 miles and 10k elevation gained. 
Instead, <a href="https://www.strava.com/activities/15429093664" target="_blank" rel="noopener noreferrer">
  my Strava activity
</a> says that I moved 25 miles and climbed 24,000 vertical feet. 
<p>
  Even worse, analyzing the raw GPX track yields an even more outlandish 42 miles traveled. 
This would be impressive, but it is blatantly wrong.
</p>

<p><img width="2412" height="1084" alt="image" src="https://github.com/user-attachments/assets/c8c0e5ee-1307-4da3-ae78-b8fde02cfc66" /></p>

<p>
  The likely issue seems to be that the GPX logging does a lot of extra zigging and zagging over short distances. 
  Looking closely at the track for the Cathedral traverse: the overall track looks good, 
</p>
<p>
  <img width="2040" height="1539" alt="image" src="https://github.com/user-attachments/assets/82da6917-3ff1-422d-9cb9-5abe3c3ac892" />
</p>
<p>
  But zooming in, there's a lot of stuff like this:
</p>
<p>
  <img width="2296" height="1264" alt="image" src="https://github.com/user-attachments/assets/96c6bc65-c063-46d6-9c9a-d78a63b824ae" />
</p>
<p>
  This is a particularly heinous section around East Prong:
</p>
<p>
  <img width="2298" height="1380" alt="image" src="https://github.com/user-attachments/assets/9df23232-139e-44ec-8470-b88e027f5b36" />
</p>

## Current fix

<p>
  My fairly simplistic solution is to enforce a minimum distance between points. A reasonable start is 10m, which means that moving along the 
GPX track, I throw out each point that is not at least 10 meters from the previous kept point. This produced this new red track:
</p>
<p>
  <img width="2106" height="1070" alt="image" src="https://github.com/user-attachments/assets/82d46d1a-21cc-4da8-81dd-4d7009e7dc31" />
  <img width="2186" height="1342" alt="image" src="https://github.com/user-attachments/assets/80692db9-ab0d-4b12-97aa-83e414ccdb29" />
</p>
<p>
  Which definitely cuts down on erroneous zigging (worth noting that for that section around East Prong, there was some real-life zigging going on as well!). 
</p>

<p>
  But what is the best minimum distance to use? Again using the Cathedral traverse track, I tested what the total distance/elevation effect
  would be at each adjustment level from 0m to 30m. First, here is the proportion of GPX points kept after each adjustment level:
</p>
<p>
  <img width="1580" height="1400" alt="image" src="https://github.com/user-attachments/assets/e7be9c91-6887-44f1-a458-fc2de642a8f5" />
</p>
<p>
  And then the overall effect on the stats:
</p>
<p>
  <img width="2000" height="1200" alt="image" src="https://github.com/user-attachments/assets/5d1f97b8-e504-493a-9ecd-418dceb5cf9c" />
</p>
<p>Going off my priors, it looks like 15 meters is the best number to use here. But does this hold in general?</p>

## Short threshold analysis

<p>
  I downloaded seven GPX tracks off of strava where I could reasonably estimate truth values for mileage and elevation, and used those to isolate a single minimum distance threshold that minimizes the mean absolute distance error across all seven. All of this logic, which involves the resampling analysis above, is contained in calibrate_gpx_threshold.py, and the sample gpx tracks I used are in the input_gpx folder. A figure summarizing the results is below:
</p>
<p>
  <img width="2000" height="1200" alt="image" src="https://github.com/user-attachments/assets/e807c372-3566-427e-8537-fdf259908b12" />
</p>
<p>
  For each minimum distance threshold from 0 to 30 meters, the average absolute distance error, average directional distance error, and the average absolute elevation error are plotted. In this analysis I prioritized the absolute distance error, which is minimized when using a 16m minimum distance threshold -- quite close to the 15m that suited the cathedral traverse track! Specific error values for each gpx track at a 16m threshold are shown below:
</p>
<p>
  <img width="2200" height="1200" alt="image" src="https://github.com/user-attachments/assets/6e7124d0-0ad9-4010-a4b8-d6400f66441f" />
</p>

## Notes on usage

### calibrate_gpx_threshold.py

<p>
  To run this script, you need paths to a folder of gpx files and to a csv file that contains 'truth' distance and elevation values. This cvs file should take on the following example structure: 

The calibration CSV should use this format:

<table>
  <thead>
    <tr>
      <th>File</th>
      <th>Mi</th>
      <th>Elev</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>cathy.gpx</td>
      <td>16</td>
      <td>11000</td>
    </tr>
    <tr>
      <td>loop.gpx</td>
      <td>28</td>
      <td>11000</td>
    </tr>
    <tr></tr>
      <td>moran.gpx</td>
      <td>20</td>
      <td>6000</td>
    </tr>
  </tbody>
</table>

</p>
<p>
  Then, to run the calibration, use this command: 
  <pre><code> python3 calibrate_gpx_threshold.py [csv_path] --gpx-dir [gpx_folder] </code></pre>
</p>
<p>
  To control the thresholds being tested, use the following: 
  <pre><code> python3 calibrate_gpx_threshold.py [csv_path] --gpx-dir [gpx_folder] --start 0 --stop 30 --step 0.5 </code></pre>
  This would conduct a threshold search starting at 0 meters, testing up to 30 meters, and going by 0.5 meter increments in between.
  Diagnostic results are written to: threshold_calibration_per_track_results.csv,
threshold_calibration_summary.csv,
threshold_calibration_summary.png, and
threshold_calibration_best_threshold_track_errors.png.
</p>

### gpx_adjuster.py

<p> This file deals with a single gpx track and, depending on provided values, outputs a modified track along with new distance/elevation figures
</p>

<p>

#### Basic usage

<pre><code> 
  python3 gpx_adjuster.py input.gpx --min-move 10 
</code></pre>

This prints the raw and adjusted distance/elevation gain, then saves a cleaned GPX file containing only the retained gpx track, using a 
minimum 10 meter distance between points.

Example output:

<table>
  <thead>
    <tr>
      <th>Metric</th>
      <th>Value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Raw distance</td>
      <td>42.22 mi</td>
    </tr>
    <tr>
      <td>Adjusted distance</td>
      <td>18.09 mi</td>
    </tr>
    <tr>
      <td>Distance difference</td>
      <td>24.13 mi</td>
    </tr>
    <tr>
      <td>Raw elevation gain</td>
      <td>92,589 ft</td>
    </tr>
    <tr>
      <td>Adjusted elevation gain</td>
      <td>23,506 ft</td>
    </tr>
    <tr>
      <td>Elevation gain difference</td>
      <td>69,083 ft</td>
    </tr>
    <tr>
      <td>Min move threshold</td>
      <td>10 m</td>
    </tr>
    <tr>
      <td>Kept points</td>
      <td>2,662 / 76,757</td>
    </tr>
    <tr>
      <td>Saved adjusted GPX</td>
      <td><code>input_adjusted_10m.gpx</code></td>
    </tr>
  </tbody>
</table>

#### Choose an output GPX filename

<pre><code>
  python3 gpx_adjuster.py input.gpx --min-move 10 --output-gpx cleaned_10m.gpx 
</code></pre>

#### Run diagnostics (similar to calibration file)

<pre><code> python3 gpx_adjuster.py input.gpx --diagnostic </code></pre>

Diagnostic mode tests thresholds from 0 m to 30 m in 2 m increments. It prints a table of adjusted distance, elevation gain, and kept-point counts at each threshold.

It also saves: input_diagnostic.png, input_kept_points_table.png 

#### Custom diagnostic thresholds

<pre><code> python3 gpx_adjuster.py input.gpx --diagnostic --thresholds 0,3,5,8,10,15,20 </code></pre>

#### Custom plot/table output paths

<pre><code> python3 gpx_adjuster.py input.gpx --diagnostic \   --plot-path diagnostic_plot.png \   --table-path kept_points_table.png 
</code></pre>

#### Optional speed filter

<pre><code> python3 gpx_adjuster.py input.gpx --min-move 10 --max-speed 20 </code></pre>

--max-speed rejects segments faster than the given speed in meters per second. This can remove large GPS jumps, though most alpine GPX overestimation is often caused by small repeated jitter rather than obvious high-speed spikes.

#### Notes

The --min-move value is in meters. A larger value removes more GPS noise but also simplifies the track more aggressively. For noisy mountain tracks, values around 8–20 m may be useful, but the best threshold depends on the device, terrain, and route.

The adjusted GPX distance should be treated as an estimate, not an exact measurement.
</p>
