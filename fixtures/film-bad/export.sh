#!/bin/bash
ffmpeg -framerate 24 -i frames/%04d.png -i assets/music.mp3 -c:v libx264 -crf 32 -s 1280x720 -c:a libmp3lame out.mp4
