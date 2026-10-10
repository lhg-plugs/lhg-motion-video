#!/bin/bash
ffmpeg -framerate 30 -i frames/%04d.png -i assets/music.mp3 -c:v libx264 -pix_fmt yuv420p -crf 18 -vf scale=1920:1080 -c:a aac -movflags +faststart -shortest out.mp4
