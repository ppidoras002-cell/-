# syntax-marker:deploy-f-generated-dockerfile-v1
FROM python:3.10
ADD https://my.deploy-f.com/f/entrypoint.sh?2 /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN curl -s https://my.deploy-f.com/f/prepare-python.sh?2 | bash -s 'false' 'false'
WORKDIR /app
COPY . /app
RUN curl -s https://my.deploy-f.com/f/install-python.sh?2 | bash -s 'false' 'true'
CMD /entrypoint.sh python3 bot.py