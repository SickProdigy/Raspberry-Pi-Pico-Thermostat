# Auto Garden 
### Growing a garden with automation and raspberry pi pico.

<p>
This will be a staging spot for all my python scripts mostly. Hopefully use this to update pico w in the future possibly? 
</p>

Other pages of concern:
- [Items Needed](https://gitea.rcs1.top/sickprodigy/Auto-Garden/wiki/Items-Needed-for-the-Project)

Note 1:
<p>
Using thonny as my IDE for micropython on raspberry pi pico w.
First thing to know is main.py will auto start with pico. Then you can call your other python scripts as needed really.
</p>

Note 2:
<p>
Grounding the RUN terminal will reset the Pico. I've jumped run to a button and the other side of the button to ground. Easy clickable reset.
</p>

Connections:
Raspberry pi is putting out 3v, use 3v-32vdc contactor/relay to switch on high voltage to fans, ac, heat, etc.

Will need to take temperatures and humidity. Want to compensate AC with outside air if possible.