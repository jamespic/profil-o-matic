#!/bin/sh
docker run --add-host "dockerhost:$(ip -4 addr show docker0 | grep -Po 'inet \K[\d\.]+')" -p 9090:9090 -v "$(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml" prom/prometheus
