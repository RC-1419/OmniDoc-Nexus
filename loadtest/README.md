# Load testing with JMeter

`omnidoc.jmx` simulates people using the API: log in once, then repeat `GET /auth/me`, `GET /providers`,
`GET /documents` and a document download. It does **not** call chat, so no AI quota is used and nothing is written.

## One-time setup (Windows)

1. Install Java 17 or newer (`java -version` should work), e.g. from adoptium.net.
2. Download **Apache JMeter** (the binary zip) from jmeter.apache.org, unzip it, and add its `bin` folder to PATH
   (or use the full path to `jmeter.bat`).

## Run it against your own computer first

```
docker compose up -d                       # database + API as usual (API on http://localhost:8000)
python -m loadtest.setup_users             # makes loadtest1..3 and loadtest/users.csv (git-ignored)
jmeter -n -t loadtest\omnidoc.jmx -l loadtest\results.jtl -e -o loadtest\report
```

Open `loadtest\report\index.html` for graphs (response times, errors, throughput).
`-o` needs a folder that does not exist or is empty: delete `loadtest\report` before a re-run.

## Settings (`-J` options, all optional)

| Option | Default | Meaning |
|---|---|---|
| `-Jthreads` | 3 | virtual users (use no more than the number of rows in users.csv) |
| `-Jrampup` | 10 | seconds to start them all |
| `-Jloops` | 20 | how many times each repeats the loop |
| `-Jthink_ms` | 500 | pause between requests |
| `-Jhost` `-Jport` `-Jprotocol` | localhost 8000 http | where the API is |
| `-Jbase_path` | /v1 | `/api/v1` when going through Caddy |
| `-Jusers_file` | loadtest/users.csv | the test users |

Example, a heavier local run: `jmeter -n -t loadtest\omnidoc.jmx -Jthreads=10 -Jloops=50 -l loadtest\results.jtl -e -o loadtest\report`
(create 10 users first: `python -m loadtest.setup_users --count 10`).

## Creating more than 5 users

Sign-up is limited to 5 per hour per address. On your own computer, start the API with a higher limit, for example
add `SIGNUP_PER_HOUR_PER_IP=100` to `.env` and restart `api`, create the users, then remove the line.

## The live site

Only with care: it is a small server shared with your real documents.
- Use few users and read-only requests (this plan only reads): `-Jthreads=2 -Jloops=10 -Jthink_ms=1000`.
- Create the users with `python -m loadtest.setup_users --base-url https://omnidocs.duckdns.org/api/v1 --allow-remote --count 2`,
  then delete them when done.
- Run: `jmeter -n -t loadtest\omnidoc.jmx -Jhost=omnidocs.duckdns.org -Jport=443 -Jprotocol=https -Jbase_path=/api/v1 -Jthreads=2 -Jloops=10 -Jthink_ms=1000 -l loadtest\results.jtl`
- Watch Prometheus (`rate(http_requests_total[1m])`) while it runs.

`results.jtl` and `report/` contain no passwords or tokens (headers are not saved), and are git-ignored anyway.
