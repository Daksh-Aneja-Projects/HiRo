#!/bin/sh
# HiRo — Dgraph schema initializer.
# Runs once at stack startup (see docker-compose `dgraph-init`). It waits for
# dgraph-alpha to be reachable, then applies the org-graph schema used by the
# graph ingestion layer (services/graph_ingestion_util.py).
set -e

DGRAPH_URL="${DGRAPH_URL:-http://dgraph-alpha:8080}"

echo "HiRo dgraph-init: waiting for ${DGRAPH_URL} ..."
i=0
until curl -sf "${DGRAPH_URL}/health" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    echo "HiRo dgraph-init: dgraph-alpha did not become healthy in time." >&2
    exit 1
  fi
  sleep 2
done

echo "HiRo dgraph-init: applying org-graph schema ..."
curl -sf -X POST "${DGRAPH_URL}/alter" -d '
  employee_id: string @index(exact) @upsert .
  full_name: string @index(term) .
  email: string @index(exact) @upsert .
  job_title: string @index(term) .
  department: string @index(exact) .
  location: string @index(exact) .
  status: string @index(exact) .
  reports_to: [uid] @reverse .

  type Employee {
    employee_id
    full_name
    email
    job_title
    department
    location
    status
    reports_to
  }
'

echo "HiRo dgraph-init: schema applied successfully."
