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
<p>Going off my priors it looks like 15 meters is the best number to use here. But does this hold in general?</p>

## Short regression analysis


