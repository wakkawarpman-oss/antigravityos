# SpiderFoot Secure Setup (Production-style)

This repository now includes an isolated SpiderFoot stack with Nginx auth.

## Added files

- docker-compose.spiderfoot.yml
- monitoring/spiderfoot/nginx/nginx.conf
- monitoring/spiderfoot/nginx/.htpasswd

## Topology

- spiderfoot service is internal-only (`expose` only)
- nginx is the only public entrypoint
- host binding is localhost only: `127.0.0.1:5001:5001`
- redis is included for queue/cache patterns

## Start/stop

- make spiderfoot-up
- make spiderfoot-logs
- make spiderfoot-down

## Credentials

- URL: http://localhost:5001
- User: admin
- Password: hanna

Change credentials by replacing `monitoring/spiderfoot/nginx/.htpasswd`.

## Install extra OSINT python packages

- make osint-tools-install

This installs optional runtime extras from requirements.osint-extra.txt
including celery, redis client, pybloom-live, scrapy, playwright, and
other OSINT helper SDKs.
