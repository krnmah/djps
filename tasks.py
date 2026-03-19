from invoke import task

@task
def run(c):
    c.run("uvicorn app.main:app --host 0.0.0.0 --port 8000")

@task
def migrate(c):
    c.run("alembic upgrade head")

@task
def revision(c):
    message = input("Enter migration message: ")
    c.run(f'alembic revision --autogenerate -m "{message}"')

@task
def docker_up(c):
    c.run("docker compose -f .\\docker\\docker-compose.yml up --build -d")

@task
def docker_down(c):
    c.run("docker compose -f .\\docker\\docker-compose.yml down")

@task
def docker_test_up(c):
    c.run("docker compose -f .\\docker\\docker-compose-test.yml up -d")

@task
def docker_test_down(c):
    c.run("docker compose -f .\\docker\\docker-compose-test.yml down -v")

@task
def run_worker(c):
    c.run("python scripts/start_worker.py")