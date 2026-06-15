.PHONY: install test api dashboard fmt up

install:        ## install backend + dashboard deps
	pip install -r backend/requirements.txt -r dashboard/requirements.txt

test:           ## run the unit tests
	python -m pytest

api:            ## run the FastAPI backend (reload)
	uvicorn backend.main:app --reload

dashboard:      ## run the Streamlit dashboard
	streamlit run dashboard/app.py

up:             ## run both services in Docker
	docker compose up --build
