.PHONY: install report test-email email

install:
	python3 -m pip install -e .

report:
	PYTHONPATH=src python3 -m dealflow_agent.run_daily --no-email

test-email:
	PYTHONPATH=src python3 -m dealflow_agent.send_test_email

email:
	PYTHONPATH=src python3 -m dealflow_agent.run_daily --email
