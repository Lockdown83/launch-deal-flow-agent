.PHONY: install report dashboard serve simulate cron-install test-email email

install:
	python3 -m pip install -e .

report:
	PYTHONPATH=src python3 -m dealflow_agent.run_daily --no-email

dashboard:
	PYTHONPATH=src python3 -m dealflow_agent.run_daily --no-email
	open reports/dashboard-latest.html

serve:
	cd reports && python3 -m http.server 8765 --bind 127.0.0.1

# Run the pipeline a few times to accumulate live run history alongside the timestamp backfill.
simulate:
	@for i in 1 2 3; do PYTHONPATH=src python3 -m dealflow_agent.run_daily --no-email >/dev/null && echo "run $$i done"; done
	open reports/dashboard-latest.html

cron-install:
	crontab cron/crontab.sample

test-email:
	PYTHONPATH=src python3 -m dealflow_agent.send_test_email

email:
	PYTHONPATH=src python3 -m dealflow_agent.run_daily --email
