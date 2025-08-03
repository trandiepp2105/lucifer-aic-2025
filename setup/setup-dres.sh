sudo apt update && sudo apt install -y openjdk-17-jdk
cd /home/trandiep/DRES && ./gradlew distZip
cd /home/trandiep/DRES/backend/build/distributions && unzip -q dres-dist.zip
cd /home/trandiep/DRES && mkdir -p data 
chmod +x /home/trandiep/DRES/backend/build/distributions/dres-dist/lib/ffmpeg/ffmpeg
chmod +x /home/trandiep/DRES/backend/build/distributions/dres-dist/lib/ffmpeg/ffprobe
# cd /home/trandiep/DRES/backend/build/distributions/dres-dist && ./bin/backend /home/trandiep/DRES/my_config.json


# run in background
cd /home/trandiep/DRES/backend/build/distributions/dres-dist && nohup ./bin/backend /home/trandiep/DRES/my_config.json > /home/trandiep/dres.log 2>&1 &

# find process ID
ps aux | grep backend | grep -v grep

# kill process
# kill <process_id>